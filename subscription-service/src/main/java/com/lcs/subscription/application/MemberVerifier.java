package com.lcs.subscription.application;

import com.lcs.subscription.infrastructure.grpc.MemberClient;
import com.lcs.subscription.infrastructure.grpc.MemberNotFoundOnRemoteException;
import io.github.resilience4j.circuitbreaker.CallNotPermittedException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.cloud.client.circuitbreaker.CircuitBreakerFactory;
import org.springframework.stereotype.Component;

// member-service 호출을 서킷브레이커로 감싼다 (D-17).
//
// 폴백 정책: fail-closed. member-service를 확인할 수 없으면 구독 생성을 거부한다.
// fail-open(그냥 통과)으로 하면 존재하지 않거나 탈퇴한 회원의 구독이 생기고,
// 그 뒤에 결제까지 진행돼 되돌리기 어려운 상태가 된다.
// 결제가 걸린 흐름에서는 가용성보다 정합성을 택한다.
@Component
public class MemberVerifier {

    private static final Logger log = LoggerFactory.getLogger(MemberVerifier.class);
    private static final String CIRCUIT_NAME = "member-service";

    private final MemberClient memberClient;
    private final CircuitBreakerFactory<?, ?> circuitBreakerFactory;

    public MemberVerifier(MemberClient memberClient, CircuitBreakerFactory<?, ?> circuitBreakerFactory) {
        this.memberClient = memberClient;
        this.circuitBreakerFactory = circuitBreakerFactory;
    }

    public void verifyActive(long memberId) {
        Boolean active = circuitBreakerFactory.create(CIRCUIT_NAME).run(
                () -> memberClient.isActiveMember(memberId),
                throwable -> {
                    // 회원 없음은 폴백이 아니라 그대로 전파한다 — 정상적인 거절 사유다.
                    if (throwable instanceof MemberNotFoundOnRemoteException e) {
                        throw e;
                    }
                    if (throwable instanceof CallNotPermittedException) {
                        log.warn("서킷 열림 — member-service 확인 불가: memberId={}", memberId);
                    } else {
                        log.warn("member-service 확인 실패: memberId={} cause={}",
                                memberId, throwable.toString());
                    }
                    throw new MemberVerificationUnavailableException();
                });

        if (!Boolean.TRUE.equals(active)) {
            throw new InactiveMemberException(memberId);
        }
    }
}
