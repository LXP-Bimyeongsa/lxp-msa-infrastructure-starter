package com.lcs.payment.infrastructure.pg;

import com.lcs.payment.application.PaymentGateway;
import com.lcs.payment.application.PgApproval;
import java.time.Duration;
import java.util.Map;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.web.client.RestTemplateBuilder;
import org.springframework.http.HttpStatusCode;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestTemplate;

/**
 * PG HTTP 어댑터 (D-39).
 *
 * <p>지금 붙는 상대는 WireMock 목이지만 통신 규격은 실제 PG와 같은 모양이다 —
 * 승인/취소 두 엔드포인트, 멱등키 전달, 거절 코드 응답.
 * 실연동 시 주소와 인증 헤더만 바꾼다.
 */
@Component
public class PgHttpClient implements PaymentGateway {

    private static final Logger log = LoggerFactory.getLogger(PgHttpClient.class);

    private final RestTemplate restTemplate;
    private final String baseUrl;

    public PgHttpClient(RestTemplateBuilder builder,
                        @Value("${pg.base-url}") String baseUrl,
                        @Value("${pg.timeout-ms:3000}") long timeoutMs) {
        // 결제는 오래 매달려 있으면 안 된다. 스케줄러 스레드가 PG 응답을 기다리며
        // 묶이면 다른 구독의 청구까지 밀린다.
        this.restTemplate = builder
                .connectTimeout(Duration.ofMillis(timeoutMs))
                .readTimeout(Duration.ofMillis(timeoutMs))
                .build();
        this.baseUrl = baseUrl;
    }

    @Override
    public PgApproval approve(String orderId, long amount, String idempotencyKey) {
        Map<String, Object> body = Map.of(
                "orderId", orderId,
                "amount", amount,
                "idempotencyKey", idempotencyKey);
        try {
            Map<?, ?> response = restTemplate.postForObject(baseUrl + "/v1/payments", body, Map.class);
            String transactionId = response == null ? null : (String) response.get("transactionId");
            if (transactionId == null) {
                // 200인데 거래 ID가 없다 = 규격이 어긋났다. 승인으로 취급하면
                // 환불할 방법이 없는 결제가 생긴다.
                log.error("PG 승인 응답에 transactionId가 없다: orderId={}", orderId);
                return PgApproval.unreachable();
            }
            return PgApproval.approved(transactionId);
        } catch (org.springframework.web.client.RestClientResponseException e) {
            return declineFrom(e, orderId);
        } catch (RestClientException e) {
            // 타임아웃·연결 실패 — 승인됐는지 알 수 없다.
            // 실패로 단정하지 않고 "모른다"로 다룬다(PgApproval.unreachable 주석 참고).
            log.error("PG 통신 실패 — 승인 여부 불명: orderId={}", orderId, e);
            return PgApproval.unreachable();
        }
    }

    private PgApproval declineFrom(org.springframework.web.client.RestClientResponseException e, String orderId) {
        HttpStatusCode status = e.getStatusCode();
        try {
            Map<?, ?> error = e.getResponseBodyAs(Map.class);
            String code = error == null ? "UNKNOWN" : String.valueOf(error.get("code"));
            boolean retryable = error != null && Boolean.TRUE.equals(error.get("retryable"));
            log.warn("PG 승인 거절: orderId={} code={} retryable={}", orderId, code, retryable);
            return PgApproval.declined(code, retryable);
        } catch (Exception parseFailure) {
            // 거절인 것은 분명한데 본문을 못 읽었다. 재시도 가능 여부를 모르므로
            // 재시도 가능으로 둔다 — 영구 거절을 재시도하는 낭비가,
            // 일시적 거절을 영구로 단정해 구독을 끊는 것보다 낫다.
            // parseFailure를 넘긴다. 이 경로는 retryable=true라 조용히 재청구를
            // 반복하는데, 원인(규격 변경·빈 본문·타입 불일치)을 안 남기면
            // 왜 계속 파싱이 깨지는지 영영 알 수 없다.
            log.warn("PG 거절 응답 파싱 실패: orderId={} status={}", orderId, status, parseFailure);
            return PgApproval.declined("UNPARSEABLE", true);
        }
    }

    @Override
    public void cancel(String transactionId) {
        try {
            restTemplate.postForObject(baseUrl + "/v1/payments/cancel",
                    Map.of("transactionId", transactionId), Map.class);
            log.info("PG 승인 취소 완료: transactionId={}", transactionId);
        } catch (RestClientException e) {
            // 환불 실패는 삼키지 않는다 — 호출 측 트랜잭션이 롤백돼
            // 다음 재시도에서 다시 시도되고, 계속 실패하면 DLQ로 간다.
            throw new PgCancelFailedException(transactionId, e);
        }
    }
}
