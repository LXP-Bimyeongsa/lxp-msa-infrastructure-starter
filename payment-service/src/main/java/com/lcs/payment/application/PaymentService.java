package com.lcs.payment.application;

import com.lcs.payment.domain.BillingSchedule;
import com.lcs.payment.domain.Payment;
import com.lcs.payment.infrastructure.outbox.OutboxWriter;
import com.lcs.payment.infrastructure.persistence.BillingScheduleRepository;
import com.lcs.payment.infrastructure.persistence.PaymentRepository;
import java.time.Duration;
import java.util.List;
import java.util.Map;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class PaymentService {

    private static final Logger log = LoggerFactory.getLogger(PaymentService.class);
    private static final String AGGREGATE = "Payment";
    private static final int FIRST_CYCLE = 1;

    private final PaymentRepository paymentRepository;
    private final BillingScheduleRepository billingScheduleRepository;
    private final OutboxWriter outboxWriter;
    private final Duration billingPeriod;

    public PaymentService(PaymentRepository paymentRepository,
                          BillingScheduleRepository billingScheduleRepository,
                          OutboxWriter outboxWriter,
                          @Value("${billing.period-days:30}") long billingPeriodDays) {
        this.paymentRepository = paymentRepository;
        this.billingScheduleRepository = billingScheduleRepository;
        this.outboxWriter = outboxWriter;
        this.billingPeriod = Duration.ofDays(billingPeriodDays);
    }

    /**
     * SubscriptionCreated 소비 — 최초 결제(1회차).
     * 성공하면 다음 회차를 예약한다 (D-25).
     */
    @Transactional
    public void processInitialPayment(String eventId, Long subscriptionId, Long memberId, Long amount) {
        if (paymentRepository.findByIdempotencyKey(eventId).isPresent()) {
            log.info("이미 처리된 결제 이벤트, 무시: eventId={}", eventId);
            return;
        }
        boolean approved = charge(eventId, subscriptionId, memberId, amount, FIRST_CYCLE);
        if (approved) {
            billingScheduleRepository.save(
                    BillingSchedule.startAfterFirstPayment(subscriptionId, memberId, amount, billingPeriod));
        }
    }

    /**
     * 스케줄러가 호출하는 정기 결제.
     * (subscriptionId, billingCycle) unique 제약이 중복 청구를 DB 수준에서 막는다 (D-26).
     */
    @Transactional
    public void processScheduledPayment(BillingSchedule schedule) {
        int cycle = schedule.getNextBillingCycle();
        // 회차 자체를 멱등키로 삼는다. 재실행돼도 같은 키가 만들어져 두 번째는 막힌다.
        String eventId = "billing-" + schedule.getSubscriptionId() + "-" + cycle;

        boolean approved = charge(eventId, schedule.getSubscriptionId(),
                schedule.getMemberId(), schedule.getAmount(), cycle);

        if (approved) {
            schedule.advance(billingPeriod);
        } else {
            // 결제 실패 시 스케줄을 멈춘다. 구독 쪽이 PaymentFailed를 받아 해지 판단을 한다.
            schedule.deactivate();
            log.warn("정기 결제 실패로 스케줄 중단: subscriptionId={} cycle={}",
                    schedule.getSubscriptionId(), cycle);
        }
        billingScheduleRepository.save(schedule);
    }

    /** 해지 — 환불(D-16) + 예약된 다음 결제 취소(D-27). */
    @Transactional
    public void cancelBillingAndRefund(Long subscriptionId) {
        billingScheduleRepository.findById(subscriptionId).ifPresent(schedule -> {
            // 남겨두면 해지된 구독이 다음 주기에 청구된다.
            schedule.deactivate();
            billingScheduleRepository.save(schedule);
        });

        List<Payment> payments = paymentRepository.findBySubscriptionIdOrderByCreatedAtDesc(subscriptionId);
        for (Payment payment : payments) {
            if (payment.refund()) {
                outboxWriter.write(AGGREGATE, String.valueOf(payment.getId()), "PaymentRefunded", Map.of(
                        "paymentId", payment.getId(),
                        "subscriptionId", subscriptionId,
                        "memberId", payment.getMemberId(),
                        "amount", payment.getAmount()
                ));
                log.info("환불 처리: paymentId={} subscriptionId={} amount={}",
                        payment.getId(), subscriptionId, payment.getAmount());
            }
        }
    }

    @Transactional(readOnly = true)
    public List<Payment> findBySubscription(Long subscriptionId) {
        return paymentRepository.findBySubscriptionIdOrderByCreatedAtDesc(subscriptionId);
    }

    /**
     * 실제 청구. PG 연동 전까지는 mock이다 (P-01).
     * PG를 붙일 때 이 메서드 안만 교체하면 된다.
     *
     * @return 승인 여부
     */
    private boolean charge(String eventId, Long subscriptionId, Long memberId, Long amount, int cycle) {
        // 선검사로 흔한 중복(재전송·재실행)을 걸러낸다.
        //
        // 제약 위반을 잡아서 무시하는 방식은 쓸 수 없다. 트랜잭션 안에서
        // DataIntegrityViolationException이 나면 그 트랜잭션은 rollback-only로
        // 표시되고, 예외를 삼킨 뒤 커밋하려 하면 UnexpectedRollbackException이 난다.
        //
        // 진짜 동시 요청이 제약에 걸리는 경우는 예외를 그대로 전파시킨다.
        // 트랜잭션이 통째로 롤백되는 것이 맞는 동작이고,
        // 스케줄러가 그 건만 로그로 남기고 다음 건으로 넘어간다.
        if (paymentRepository.existsBySubscriptionIdAndBillingCycle(subscriptionId, cycle)) {
            log.info("이미 청구된 회차, 무시: subscriptionId={} cycle={}", subscriptionId, cycle);
            return false;
        }

        boolean approved = amount != null && amount > 0;
        Payment payment = approved
                ? Payment.approved(subscriptionId, memberId, amount, eventId, cycle)
                : Payment.failed(subscriptionId, memberId, amount == null ? 0 : amount, eventId, cycle);

        paymentRepository.saveAndFlush(payment);

        if (approved) {
            outboxWriter.write(AGGREGATE, String.valueOf(payment.getId()), "PaymentCompleted", Map.of(
                    "paymentId", payment.getId(),
                    "subscriptionId", subscriptionId,
                    "memberId", memberId,
                    "amount", amount,
                    "billingCycle", cycle
            ));
        } else {
            outboxWriter.write(AGGREGATE, String.valueOf(payment.getId()), "PaymentFailed", Map.of(
                    "paymentId", payment.getId(),
                    "subscriptionId", subscriptionId,
                    "memberId", memberId,
                    "billingCycle", cycle,
                    "reason", "invalid amount"
            ));
        }
        return approved;
    }
}
