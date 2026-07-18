package com.lcs.subscription.application;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.willThrow;

import com.lcs.subscription.infrastructure.grpc.MemberCallRejectedException;
import com.lcs.subscription.infrastructure.grpc.MemberClient;
import com.lcs.subscription.infrastructure.grpc.MemberNotFoundOnRemoteException;
import com.lcs.subscription.infrastructure.grpc.MemberServiceUnavailableException;
import io.github.resilience4j.circuitbreaker.CircuitBreaker;
import io.github.resilience4j.circuitbreaker.CircuitBreakerRegistry;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.bean.override.mockito.MockitoBean;

@SpringBootTest
@ActiveProfiles("test")
class MemberVerifierTest {

    @Autowired
    private MemberVerifier memberVerifier;

    @Autowired
    private CircuitBreakerRegistry circuitBreakerRegistry;

    @MockitoBean
    private MemberClient memberClient;

    @BeforeEach
    void resetCircuit() {
        // find()를 써야 한다. circuitBreaker(name)은 없으면 "기본 설정으로 생성"하는데,
        // 그러면 팩토리가 커스텀 설정으로 등록하기 전에 선점돼
        // minimumNumberOfCalls=100(기본값)짜리 서킷이 만들어진다.
        circuitBreakerRegistry.find("member-service").ifPresent(CircuitBreaker::reset);
    }

    @Test
    @DisplayName("활성 회원이면 통과한다")
    void passesForActiveMember() {
        given(memberClient.isActiveMember(1L)).willReturn(true);

        memberVerifier.verifyActive(1L);
    }

    @Test
    @DisplayName("탈퇴 회원이면 거부한다")
    void rejectsInactiveMember() {
        given(memberClient.isActiveMember(2L)).willReturn(false);

        assertThatThrownBy(() -> memberVerifier.verifyActive(2L))
                .isInstanceOf(InactiveMemberException.class);
    }

    @Test
    @DisplayName("없는 회원은 그대로 전파된다 — 폴백으로 삼키지 않는다")
    void propagatesNotFound() {
        willThrow(new MemberNotFoundOnRemoteException(3L))
                .given(memberClient).isActiveMember(3L);

        assertThatThrownBy(() -> memberVerifier.verifyActive(3L))
                .isInstanceOf(MemberNotFoundOnRemoteException.class);
    }

    @Test
    @DisplayName("통신 실패 시 fail-closed — 503으로 이어지는 예외를 던진다")
    void failsClosedOnRemoteFailure() {
        willThrow(new MemberServiceUnavailableException("boom", null))
                .given(memberClient).isActiveMember(4L);

        assertThatThrownBy(() -> memberVerifier.verifyActive(4L))
                .isInstanceOf(MemberVerificationUnavailableException.class);
    }

    @Test
    @DisplayName("연속 실패가 임계치를 넘으면 서킷이 열린다")
    void opensCircuitAfterRepeatedFailures() {
        willThrow(new MemberServiceUnavailableException("boom", null))
                .given(memberClient).isActiveMember(anyLong());

        // minimumNumberOfCalls=5, failureRateThreshold=50%
        for (int i = 0; i < 10; i++) {
            try {
                memberVerifier.verifyActive(99L);
            } catch (MemberVerificationUnavailableException ignored) {
                // 폴백 동작 확인이 목적이라 여기서는 무시한다
            }
        }

        CircuitBreaker circuitBreaker = circuitBreakerRegistry.circuitBreaker("member-service");
        assertThat(circuitBreaker.getState()).isEqualTo(CircuitBreaker.State.OPEN);
    }

    @Test
    @DisplayName("자격증명 거절도 fail-closed — 회원을 확인 못 했으면 구독을 만들지 않는다(D-34)")
    void failsClosedOnCredentialRejection() {
        willThrow(new MemberCallRejectedException("토큰 거절", null))
                .given(memberClient).isActiveMember(6L);

        assertThatThrownBy(() -> memberVerifier.verifyActive(6L))
                .isInstanceOf(MemberVerificationUnavailableException.class);
    }

    @Test
    @DisplayName("자격증명 거절은 서킷 집계에서 제외된다 — 상대는 멀쩡한데 서킷을 열면 안 된다(D-34)")
    void credentialRejectionDoesNotOpenCircuit() {
        // 시크릿 설정이 틀린 상황. member-service는 정상 동작하며 거절만 하고 있다.
        // 이걸 장애로 세면 멀쩡한 서비스의 서킷이 열리고 진짜 원인이 묻힌다.
        willThrow(new MemberCallRejectedException("토큰 거절", null))
                .given(memberClient).isActiveMember(anyLong());

        for (int i = 0; i < 10; i++) {
            try {
                memberVerifier.verifyActive(7L);
            } catch (MemberVerificationUnavailableException ignored) {
                // fail-closed는 유지된다 — 집계에서만 빠진다
            }
        }

        CircuitBreaker circuitBreaker = circuitBreakerRegistry.circuitBreaker("member-service");
        assertThat(circuitBreaker.getState()).isEqualTo(CircuitBreaker.State.CLOSED);
    }

    @Test
    @DisplayName("회원 없음은 서킷 집계에서 제외된다 — 잘못된 요청으로 서킷이 열리면 안 된다")
    void notFoundDoesNotOpenCircuit() {
        willThrow(new MemberNotFoundOnRemoteException(5L))
                .given(memberClient).isActiveMember(anyLong());

        for (int i = 0; i < 10; i++) {
            try {
                memberVerifier.verifyActive(5L);
            } catch (MemberNotFoundOnRemoteException ignored) {
                // 정상적인 거절 사유
            }
        }

        CircuitBreaker circuitBreaker = circuitBreakerRegistry.circuitBreaker("member-service");
        assertThat(circuitBreaker.getState()).isEqualTo(CircuitBreaker.State.CLOSED);
    }
}
