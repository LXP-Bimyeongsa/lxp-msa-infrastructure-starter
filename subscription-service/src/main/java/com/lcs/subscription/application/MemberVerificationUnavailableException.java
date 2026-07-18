package com.lcs.subscription.application;

// 회원 확인 자체가 불가능한 상태(원격 장애·서킷 열림). 503으로 응답한다.
public class MemberVerificationUnavailableException extends RuntimeException {

    public MemberVerificationUnavailableException() {
        super("회원 확인 서비스를 사용할 수 없습니다. 잠시 후 다시 시도해 주세요.");
    }
}
