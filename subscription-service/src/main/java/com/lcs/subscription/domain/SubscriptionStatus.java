package com.lcs.subscription.domain;

public enum SubscriptionStatus {
    PENDING,    // 생성됨, 결제 대기
    ACTIVE,     // 결제 완료
    CANCELLED   // 결제 실패 보상 또는 해지
}
