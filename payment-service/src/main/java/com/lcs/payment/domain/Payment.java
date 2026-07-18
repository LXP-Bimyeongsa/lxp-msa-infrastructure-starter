package com.lcs.payment.domain;

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
@Table(name = "payment")
public class Payment {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "subscription_id", nullable = false)
    private Long subscriptionId;

    @Column(name = "member_id", nullable = false)
    private Long memberId;

    @Column(nullable = false)
    private Long amount;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 20)
    private PaymentStatus status;

    // 사가 이벤트의 outbox UUID. at-least-once 재전송이 와도
    // unique 제약이 두 번째 INSERT를 막는다.
    @Column(name = "idempotency_key", nullable = false, unique = true, length = 36)
    private String idempotencyKey;

    // 회차. (subscription_id, billing_cycle)에 unique 제약이 있다 (D-26).
    // 이벤트 UUID 멱등키는 "같은 이벤트의 재전송"을 막고,
    // 이 조합은 "같은 회차를 다른 경로로 다시 청구하는 것"을 막는다.
    // 스케줄러가 다중 인스턴스로 돌아도 회차당 한 건만 남는다.
    @Column(name = "billing_cycle", nullable = false)
    private Integer billingCycle;

    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt;

    @Column(name = "refunded_at")
    private Instant refundedAt;

    protected Payment() {
        // JPA 전용
    }

    private Payment(Long subscriptionId, Long memberId, Long amount,
                    PaymentStatus status, String idempotencyKey, int billingCycle) {
        this.subscriptionId = subscriptionId;
        this.memberId = memberId;
        this.amount = amount;
        this.status = status;
        this.idempotencyKey = idempotencyKey;
        this.billingCycle = billingCycle;
        this.createdAt = Instant.now();
    }

    public static Payment approved(Long subscriptionId, Long memberId, Long amount,
                                   String idempotencyKey, int billingCycle) {
        return new Payment(subscriptionId, memberId, amount, PaymentStatus.APPROVED,
                idempotencyKey, billingCycle);
    }

    public static Payment failed(Long subscriptionId, Long memberId, Long amount,
                                 String idempotencyKey, int billingCycle) {
        return new Payment(subscriptionId, memberId, amount, PaymentStatus.FAILED,
                idempotencyKey, billingCycle);
    }

    /** 환불. 멱등 — 이미 REFUNDED면 false. APPROVED 상태만 환불 가능. */
    public boolean refund() {
        if (status != PaymentStatus.APPROVED) {
            return false;
        }
        this.status = PaymentStatus.REFUNDED;
        this.refundedAt = Instant.now();
        return true;
    }

    public Long getId() {
        return id;
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

    public PaymentStatus getStatus() {
        return status;
    }

    public String getIdempotencyKey() {
        return idempotencyKey;
    }

    public Integer getBillingCycle() {
        return billingCycle;
    }
}
