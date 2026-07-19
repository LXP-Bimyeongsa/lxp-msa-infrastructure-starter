package com.lcs.payment.application;

import com.lcs.common.outbox.OutboxWriter;
import com.lcs.payment.domain.BillingSchedule;
import com.lcs.payment.domain.Payment;
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
    private final int maxDunningAttempts;
    private final Duration dunningRetryInterval;

    public PaymentService(PaymentRepository paymentRepository,
                          BillingScheduleRepository billingScheduleRepository,
                          OutboxWriter outboxWriter,
                          @Value("${billing.period-days:30}") long billingPeriodDays,
                          // 재시도 횟수·간격은 사업 정책이지 코드가 정할 것이 아니다 (D-37).
                          // 기본값은 "3일 간격 3회"로, 카드 한도가 풀릴 만한 시간을 준다.
                          @Value("${billing.dunning.max-attempts:3}") int maxDunningAttempts,
                          @Value("${billing.dunning.retry-interval-seconds:259200}") long retryIntervalSeconds) {
        this.paymentRepository = paymentRepository;
        this.billingScheduleRepository = billingScheduleRepository;
        this.outboxWriter = outboxWriter;
        this.billingPeriod = Duration.ofDays(billingPeriodDays);
        this.maxDunningAttempts = maxDunningAttempts;
        this.dunningRetryInterval = Duration.ofSeconds(retryIntervalSeconds);
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
        // 1회차 실패는 재시도하지 않는다 (D-37) — 아직 아무것도 제공하지 않은 상태라
        // 즉시 취소가 맞다. PaymentFailed를 그대로 발행해 subscription이 보상하게 둔다.
        boolean approved = charge(eventId, subscriptionId, memberId, amount, FIRST_CYCLE, true);
        if (approved) {
            billingScheduleRepository.save(
                    BillingSchedule.startAfterFirstPayment(subscriptionId, memberId, amount, billingPeriod));
        }
    }

    /**
     * 스케줄러가 호출하는 정기 결제.
     * (subscriptionId, billingCycle) unique 제약이 중복 청구를 DB 수준에서 막는다 (D-26).
     *
     * <p>실패해도 바로 해지하지 않는다 (D-37). 카드 한도 초과·일시적 승인 거절처럼
     * 며칠 뒤면 풀리는 사유가 흔하고, 이미 서비스를 쓰고 있던 회원을 한 번의 실패로
     * 끊는 것은 과하다. 정해진 횟수만큼 재시도한 뒤에야 포기한다.
     *
     * <p><b>최초 결제(1회차)와 다르게 다루는 이유</b> — 1회차 실패는 아직 아무것도
     * 제공하지 않은 상태라 즉시 취소가 맞다(기존 동작 유지). 정기 결제 실패는
     * 이미 제공 중인 서비스를 끊는 문제다.
     */
    @Transactional
    public void processScheduledPayment(BillingSchedule schedule) {
        int cycle = schedule.getNextBillingCycle();
        // 회차 자체를 멱등키로 삼는다. 재실행돼도 같은 키가 만들어져 두 번째는 막힌다.
        String eventId = "billing-" + schedule.getSubscriptionId() + "-" + cycle;

        // 재시도가 남아 있으면 실패 이벤트를 내지 않는다 — subscription이 받으면 해지해버린다.
        boolean lastChance = schedule.retriesExhausted(maxDunningAttempts - 1);
        boolean approved = charge(eventId, schedule.getSubscriptionId(),
                schedule.getMemberId(), schedule.getAmount(), cycle, lastChance);

        if (approved) {
            schedule.advance(billingPeriod);
        } else if (lastChance) {
            // 재시도를 다 썼다. 이제야 스케줄을 멈추고, 위 charge()가 발행한
            // PaymentFailed를 subscription이 받아 해지한다.
            schedule.deactivate();
            log.warn("정기 결제 재시도 소진으로 스케줄 중단: subscriptionId={} cycle={} 시도={}회",
                    schedule.getSubscriptionId(), cycle, maxDunningAttempts);
        } else {
            schedule.scheduleRetry(dunningRetryInterval);
            log.info("정기 결제 실패, 재시도 예정: subscriptionId={} cycle={} {}/{}회 다음={}",
                    schedule.getSubscriptionId(), cycle,
                    schedule.getRetryCount(), maxDunningAttempts, schedule.getNextBillingAt());
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
    private boolean charge(String eventId, Long subscriptionId, Long memberId, Long amount, int cycle,
                           boolean terminalOnFailure) {
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

        if (!approved && !terminalOnFailure) {
            // 재시도가 남은 실패는 Payment 행으로 남기지 않는다 (D-37).
            //
            // (subscription_id, billing_cycle) unique 제약(D-26) 때문이다 —
            // 실패 행을 써버리면 같은 회차의 재시도가 제약에 막혀 영영 성공할 수 없다.
            //
            // 중복 청구 방지는 그대로다: 실제로 승인된 건만 행이 생기고,
            // 그 순간부터 같은 회차는 제약이 막는다. 시도 횟수는 스케줄의 retry_count가 센다.
            log.info("정기 결제 승인 거절(재시도 예정): subscriptionId={} cycle={}", subscriptionId, cycle);
            return false;
        }

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
