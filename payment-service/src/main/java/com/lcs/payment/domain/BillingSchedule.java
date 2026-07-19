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

    // 현재 회차에서 실패한 횟수 (D-37). 성공하면 0으로 돌아간다.
    // 스케줄에 두는 이유 — 재시도는 "이 구독의 이번 회차" 상태지 결제 건의 속성이 아니다.
    @Column(name = "retry_count", nullable = false)
    private int retryCount;

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
        this.retryCount = 0;
    }

    /** 최초 결제 성공 시 다음 회차를 예약한다. */
    public static BillingSchedule startAfterFirstPayment(Long subscriptionId, Long memberId,
                                                         Long amount, Duration period) {
        return new BillingSchedule(subscriptionId, memberId, amount, 2, Instant.now().plus(period));
    }

    /** 회차 청구 후 다음 회차로 넘긴다. */
    public void advance(Duration period) {
        this.nextBillingCycle += 1;
        // 다음 청구일은 "지금"이 아니라 "예정일" 기준으로 더한다.
        // 실패로 재시도가 밀렸어도 청구 주기가 뒤로 밀리지 않는다.
        this.nextBillingAt = this.nextBillingAt.plus(period);
        // 이번 회차는 끝났다. 다음 회차는 깨끗한 상태에서 시작한다 (D-37).
        this.retryCount = 0;
    }

    /**
     * 실패한 회차를 재시도로 미룬다 (D-37).
     *
     * <p>재시도 간격은 예정일이 아니라 <b>지금</b>부터 잰다 — 이미 지난 예정일에
     * 더하면 간격이 0이 되어 스케줄러가 곧바로 다시 집는다.
     */
    public void scheduleRetry(Duration retryInterval) {
        this.retryCount += 1;
        this.nextBillingAt = Instant.now().plus(retryInterval);
    }

    /** 재시도를 다 썼는가 (D-37). */
    public boolean retriesExhausted(int maxAttempts) {
        return this.retryCount >= maxAttempts;
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

    public int getRetryCount() {
        return retryCount;
    }
}
