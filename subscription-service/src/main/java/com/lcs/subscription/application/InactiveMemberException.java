package com.lcs.subscription.application;

// 회원은 존재하지만 활성 상태가 아니다(탈퇴 등).
public class InactiveMemberException extends RuntimeException {

    public InactiveMemberException(long memberId) {
        super("활성 회원이 아닙니다: memberId=" + memberId);
    }
}
