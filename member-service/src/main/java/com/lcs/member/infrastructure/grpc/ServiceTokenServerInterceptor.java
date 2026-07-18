package com.lcs.member.infrastructure.grpc;

import io.grpc.Metadata;
import io.grpc.ServerCall;
import io.grpc.ServerCallHandler;
import io.grpc.ServerInterceptor;
import io.grpc.Status;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.security.oauth2.jwt.JwtDecoder;
import org.springframework.stereotype.Component;

/**
 * gRPC 호출도 서비스 토큰을 요구한다 (D-34).
 *
 * <p>D-33이 REST 경로를 막았지만 gRPC 포트(9092)는 그대로 열려 있었다.
 * 회원 정보 조회는 REST든 gRPC든 같은 데이터인데 한쪽만 막으면 막지 않은 것과 같다.
 *
 * <p>검증은 {@code common-security}의 {@code JwtDecoder}가 한다 — 서명·issuer·audience를
 * REST와 동일한 규칙으로 본다. 두 경로가 다른 규칙을 쓰면 어느 쪽이 느슨한지
 * 추적할 수 없게 된다.
 */
@Component
public class ServiceTokenServerInterceptor implements ServerInterceptor {

    static final Metadata.Key<String> AUTHORIZATION =
            Metadata.Key.of("authorization", Metadata.ASCII_STRING_MARSHALLER);

    private static final Logger log = LoggerFactory.getLogger(ServiceTokenServerInterceptor.class);
    private static final String BEARER = "Bearer ";

    private final JwtDecoder jwtDecoder;

    public ServiceTokenServerInterceptor(JwtDecoder jwtDecoder) {
        this.jwtDecoder = jwtDecoder;
    }

    @Override
    public <R, S> ServerCall.Listener<R> interceptCall(ServerCall<R, S> call,
                                                       Metadata headers,
                                                       ServerCallHandler<R, S> next) {
        String authorization = headers.get(AUTHORIZATION);
        if (authorization == null || !authorization.startsWith(BEARER)) {
            return reject(call, "서비스 토큰이 없습니다");
        }

        try {
            jwtDecoder.decode(authorization.substring(BEARER.length()));
        } catch (Exception e) {
            // 서명 불일치·만료·audience 불일치를 구분하지 않는다.
            // 구체적으로 알려주면 공격자에게 힌트가 된다. 원인은 서버 로그에만 남긴다.
            log.warn("gRPC 서비스 토큰 검증 실패: {}", e.getMessage());
            return reject(call, "유효하지 않은 서비스 토큰입니다");
        }

        return next.startCall(call, headers);
    }

    private <R, S> ServerCall.Listener<R> reject(ServerCall<R, S> call, String description) {
        // UNAUTHENTICATED를 쓰는 이유 — 호출 측이 "이건 member-service 장애가 아니라
        // 내 자격증명 문제"로 분류할 수 있어야 한다. UNAVAILABLE로 내리면
        // 호출 측 서킷브레이커가 멀쩡한 서비스를 죽은 것으로 센다.
        call.close(Status.UNAUTHENTICATED.withDescription(description), new Metadata());
        return new ServerCall.Listener<>() {
        };
    }
}
