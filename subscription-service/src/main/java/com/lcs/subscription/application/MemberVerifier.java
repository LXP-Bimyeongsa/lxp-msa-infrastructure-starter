package com.lcs.subscription.application;

import com.lcs.subscription.infrastructure.grpc.MemberCallRejectedException;
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
                    if (throwable instanceof MemberCallRejectedException) {
                        // 상대는 멀쩡한데 우리 자격증명이 거절됐다 (D-34).
                        // member-service 장애로 읽으면 엉뚱한 곳을 보게 되므로 따로 남긴다.
                        // 서킷 집계에서는 빠지지만(CircuitBreakerConfiguration) 요청은 거절한다.
                        // toString()이 아니라 예외 자체를 넘긴다 — 이 예외는
                        // StatusRuntimeException을 감싸고 있고, gRPC 상태와 서버가 보낸
                        // 메시지는 그 cause에만 있다. 잘라내면 "설정을 확인하라"는
                        // 말만 남고 무엇을 확인할지가 사라진다.
                        log.error("서비스 토큰 거절 — 설정을 확인해야 한다: memberId={}",
                                memberId, throwable);
                    } else if (throwable instanceof CallNotPermittedException) {
                        // 서킷이 열린 것은 이미 아래 분기에서 원인을 남긴 뒤의 결과다.
                        // 여기서 스택트레이스를 또 찍으면 열려 있는 동안 로그만 채운다.
                        log.warn("서킷 열림 — member-service 확인 불가: memberId={}", memberId);
                    } else {
                        // 진짜 통신 장애가 들어오는 곳이다. 원인 없이 warn 한 줄이면
                        // 서킷이 왜 열렸는지 되짚을 근거가 남지 않는다.
                        log.warn("member-service 확인 실패: memberId={}", memberId, throwable);
                    }
                    throw new MemberVerificationUnavailableException();
                });

        if (!Boolean.TRUE.equals(active)) {
            throw new InactiveMemberException(memberId);
        }
    }
}
