package com.lcs.subscription.domain;

public enum SubscriptionPlan {
    BASIC(29_000L),
    PREMIUM(49_000L);

    private final long price;

    SubscriptionPlan(long price) {
        this.price = price;
    }

    public long getPrice() {
        return price;
    }
}
