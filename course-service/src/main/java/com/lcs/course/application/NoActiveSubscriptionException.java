package com.lcs.course.application;

// 활성 구독이 없어 재생 URL을 발급하지 않는다 (D-36, P-16).
//
// 404가 아니라 403이다 — 강의는 존재하고 회원도 정상이며, 구독만 없다.
// 404로 감추면 "없는 강의"와 구분이 안 돼 사용자가 구독하면 볼 수 있다는 것을 모른다.
public class NoActiveSubscriptionException extends RuntimeException {

    public NoActiveSubscriptionException(Long memberId) {
        super("활성 구독이 없습니다: memberId=" + memberId);
    }
}
