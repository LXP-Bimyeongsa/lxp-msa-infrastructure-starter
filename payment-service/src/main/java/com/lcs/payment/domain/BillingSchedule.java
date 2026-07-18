package com.lcs.payment.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.Duration;
import java.time.Instant;

// 정기 결제 스케줄. payment-service가 소유한다 (D-25).
@Entity
@Table(name = "billing_schedule")
public class BillingSchedule {

    @Id
    @Column(name = "subscription_id")
    private Long subscriptionId;

    @Column(name = "member_id", nullable = false)
    private Long memberId;

    @Column(nullable = false)
    private Long amount;

    // 다음에 청구할 회차. payment의 (subscription_id, billing_cycle) 멱등키와 짝을 이룬다.
    @Column(name = "next_billing_cycle", nullable = false)
    private Integer nextBillingCycle;

    @Column(name = "next_billing_at", nullable = false)
    private Instant nextBillingAt;

    @Column(nullable = false)
    private boolean active;

    protected BillingSchedule() {
        // JPA 전용
    }

    private BillingSchedule(Long subscriptionId, Long memberId, Long amount,
                            int nextBillingCycle, Instant nextBillingAt) {
        this.subscriptionId = subscriptionId;
        this.memberId = memberId;
        this.amount = amount;
        this.nextBillingCycle = nextBillingCycle;
        this.nextBillingAt = nextBillingAt;
        this.active = true;
    }

    /** 최초 결제 성공 시 다음 회차를 예약한다. */
    public static BillingSchedule startAfterFirstPayment(Long subscriptionId, Long memberId,
                                                         Long amount, Duration period) {
        return new BillingSchedule(subscriptionId, memberId, amount, 2, Instant.now().plus(period));
    }

    /** 회차 청구 후 다음 회차로 넘긴다. */
    public void advance(Duration period) {
        this.nextBillingCycle += 1;
        this.nextBillingAt = this.nextBillingAt.plus(period);
    }

    /**
     * 해지 시 즉시 중단한다 (D-27).
     * 남겨두면 다음 주기에 해지된 구독이 청구된다.
     */
    public void deactivate() {
        this.active = false;
    }

    public Long getSubscriptionId() {
        return subscriptionId;
    }

    public Long getMemberId() {
        return memberId;
    }

    public Long getAmount() {
        return amount;
    }

    public Integer getNextBillingCycle() {
        return nextBillingCycle;
    }

    public Instant getNextBillingAt() {
        return nextBillingAt;
    }

    public boolean isActive() {
        return active;
    }
}
