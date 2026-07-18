package com.lcs.subscription.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.Instant;

@Entity
@Table(name = "subscription")
public class Subscription {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "member_id", nullable = false)
    private Long memberId;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 20)
    private SubscriptionPlan plan;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 20)
    private SubscriptionStatus status;

    // 결제 금액은 생성 시점의 플랜 가격으로 고정한다.
    // 플랜 가격이 나중에 바뀌어도 이미 만들어진 구독의 금액은 변하지 않아야 한다.
    @Column(nullable = false)
    private Long amount;

    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt;

    @Column(name = "activated_at")
    private Instant activatedAt;

    @Column(name = "cancelled_at")
    private Instant cancelledAt;

    protected Subscription() {
        // JPA 전용
    }

    private Subscription(Long memberId, SubscriptionPlan plan) {
        this.memberId = memberId;
        this.plan = plan;
        this.status = SubscriptionStatus.PENDING;
        this.amount = plan.getPrice();
        this.createdAt = Instant.now();
    }

    public static Subscription request(Long memberId, SubscriptionPlan plan) {
        return new Subscription(memberId, plan);
    }

    /** PaymentCompleted 수신 시. PENDING이 아닌 상태(이미 해지 등)면 false를 돌려주고 무시한다. */
    public boolean activate() {
        if (status != SubscriptionStatus.PENDING) {
            return false;
        }
        this.status = SubscriptionStatus.ACTIVE;
        this.activatedAt = Instant.now();
        return true;
    }

    /** 해지. 멱등 — 이미 CANCELLED면 false. */
    public boolean cancel() {
        if (status == SubscriptionStatus.CANCELLED) {
            return false;
        }
        this.status = SubscriptionStatus.CANCELLED;
        this.cancelledAt = Instant.now();
        return true;
    }

    public boolean isOwnedBy(Long candidateMemberId) {
        return this.memberId.equals(candidateMemberId);
    }

    public Long getId() {
        return id;
    }

    public Long getMemberId() {
        return memberId;
    }

    public SubscriptionPlan getPlan() {
        return plan;
    }

    public SubscriptionStatus getStatus() {
        return status;
    }

    public Long getAmount() {
        return amount;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }
}
