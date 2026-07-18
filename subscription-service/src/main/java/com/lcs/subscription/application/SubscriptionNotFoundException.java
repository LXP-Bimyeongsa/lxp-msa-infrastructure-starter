package com.lcs.subscription.application;

public class SubscriptionNotFoundException extends RuntimeException {

    public SubscriptionNotFoundException(Long id) {
        super("구독을 찾을 수 없습니다: id=" + id);
    }
}
