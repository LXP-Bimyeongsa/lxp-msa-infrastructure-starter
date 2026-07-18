package com.lcs.subscription.infrastructure.grpc;

/**
 * member-service가 우리 자격증명을 거절했다 (D-34).
 *
 * <p>{@link MemberServiceUnavailableException}과 반드시 구분한다 —
 * 이건 <b>상대가 멀쩡하다는 증거</b>다. 요청을 받아서 판단하고 거절했기 때문이다.
 * 장애로 세면 시크릿 설정이 틀렸을 때 멀쩡한 member-service의 서킷이 열리고,
 * 진짜 원인(우리 쪽 자격증명)은 서킷 로그에 묻힌다.
 *
 * <p>다만 결과는 여전히 fail-closed다 — 회원을 확인하지 못한 채로
 * 구독을 만들 수는 없다(D-18). 서킷에 세지 않을 뿐 요청은 거절된다.
 */
public class MemberCallRejectedException extends RuntimeException {

    public MemberCallRejectedException(String message, Throwable cause) {
        super(message, cause);
    }
}
