package com.lcs.payment.infrastructure.scheduler;

import com.lcs.payment.application.PaymentService;
import com.lcs.payment.domain.BillingSchedule;
import com.lcs.payment.infrastructure.persistence.BillingScheduleRepository;
import java.time.Instant;
import java.util.List;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

// 정기 결제 트리거 (D-25).
//
// 인스턴스가 여러 개면 같은 스케줄을 동시에 집을 수 있다. 그래서 분산 락에
// 기대지 않고, (subscriptionId, billingCycle) unique 제약이 중복 청구를
// DB 수준에서 막도록 설계했다 (D-26). 락은 성능 최적화지 정합성의 근거가 아니다.
@Component
@ConditionalOnProperty(name = "billing.scheduler.enabled", havingValue = "true", matchIfMissing = true)
public class BillingScheduler {

    private static final Logger log = LoggerFactory.getLogger(BillingScheduler.class);

    private final BillingScheduleRepository billingScheduleRepository;
    private final PaymentService paymentService;

    public BillingScheduler(BillingScheduleRepository billingScheduleRepository,
                            PaymentService paymentService) {
        this.billingScheduleRepository = billingScheduleRepository;
        this.paymentService = paymentService;
    }

    @Scheduled(fixedDelayString = "${billing.scheduler.interval-ms:60000}")
    public void chargeDueSubscriptions() {
        List<BillingSchedule> due = billingScheduleRepository
                .findTop100ByActiveTrueAndNextBillingAtBeforeOrderByNextBillingAtAsc(Instant.now());
        if (due.isEmpty()) {
            return;
        }
        log.info("정기 결제 대상 {}건", due.size());
        for (BillingSchedule schedule : due) {
            try {
                paymentService.processScheduledPayment(schedule);
            } catch (Exception e) {
                // 한 건이 실패해도 나머지는 계속 처리한다.
                // 실패한 건은 next_billing_at이 그대로라 다음 폴링에서 다시 잡힌다.
                log.error("정기 결제 처리 실패: subscriptionId={}", schedule.getSubscriptionId(), e);
            }
        }
    }
}
