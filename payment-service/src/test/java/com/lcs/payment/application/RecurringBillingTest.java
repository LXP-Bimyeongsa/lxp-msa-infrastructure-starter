package com.lcs.payment.application;

import static org.assertj.core.api.Assertions.assertThat;

import com.lcs.common.outbox.OutboxRepository;
import com.lcs.payment.domain.BillingSchedule;
import com.lcs.payment.domain.PaymentStatus;
import com.lcs.payment.infrastructure.persistence.BillingScheduleRepository;
import java.util.UUID;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;

@SpringBootTest
@ActiveProfiles("test")
class RecurringBillingTest {

    @Autowired
    private PaymentService paymentService;

    @Autowired
    private BillingScheduleRepository billingScheduleRepository;

    @Autowired
    private OutboxRepository outboxRepository;

    @Test
    @DisplayName("최초 결제가 승인되면 다음 회차가 예약된다")
    void firstPaymentSchedulesNextCycle() {
        paymentService.processInitialPayment(UUID.randomUUID().toString(), 100L, 1L, 29_000L);

        BillingSchedule schedule = billingScheduleRepository.findById(100L).orElseThrow();
        assertThat(schedule.isActive()).isTrue();
        assertThat(schedule.getNextBillingCycle()).isEqualTo(2);
        assertThat(schedule.getNextBillingAt()).isNotNull();
    }

    @Test
    @DisplayName("결제가 실패하면 스케줄을 만들지 않는다")
    void failedFirstPaymentSchedulesNothing() {
        paymentService.processInitialPayment(UUID.randomUUID().toString(), 101L, 1L, 0L);

        assertThat(billingScheduleRepository.findById(101L)).isEmpty();
    }

    @Test
    @DisplayName("정기 결제를 처리하면 회차가 올라간다")
    void scheduledPaymentAdvancesCycle() {
        paymentService.processInitialPayment(UUID.randomUUID().toString(), 102L, 1L, 29_000L);
        BillingSchedule schedule = billingScheduleRepository.findById(102L).orElseThrow();

        paymentService.processScheduledPayment(schedule);

        BillingSchedule after = billingScheduleRepository.findById(102L).orElseThrow();
        assertThat(after.getNextBillingCycle()).isEqualTo(3);
        assertThat(paymentService.findBySubscription(102L)).hasSize(2);
    }

    @Test
    @DisplayName("같은 회차를 두 번 청구하면 두 번째는 DB 제약으로 막힌다 (D-26)")
    void sameCycleChargedOnlyOnce() {
        paymentService.processInitialPayment(UUID.randomUUID().toString(), 103L, 1L, 29_000L);
        BillingSchedule schedule = billingScheduleRepository.findById(103L).orElseThrow();

        paymentService.processScheduledPayment(schedule);
        // 스케줄러 다중 인스턴스가 같은 스케줄(회차 2)을 동시에 집은 상황
        BillingSchedule stale = staleCopyOfCycle2(103L);
        paymentService.processScheduledPayment(stale);

        // 1회차 + 2회차 = 2건. 2회차가 두 번 청구되지 않았다.
        assertThat(paymentService.findBySubscription(103L)).hasSize(2);
        long cycle2Count = paymentService.findBySubscription(103L).stream()
                .filter(p -> p.getBillingCycle() == 2)
                .count();
        assertThat(cycle2Count).isEqualTo(1);
    }

    @Test
    @DisplayName("해지하면 예약된 다음 결제가 즉시 중단된다 (D-27)")
    void cancellationStopsScheduledBilling() {
        paymentService.processInitialPayment(UUID.randomUUID().toString(), 104L, 1L, 29_000L);
        assertThat(billingScheduleRepository.findById(104L).orElseThrow().isActive()).isTrue();

        paymentService.cancelBillingAndRefund(104L);

        assertThat(billingScheduleRepository.findById(104L).orElseThrow().isActive()).isFalse();
    }

    @Test
    @DisplayName("해지 시 환불도 함께 처리된다")
    void cancellationRefundsPayment() {
        paymentService.processInitialPayment(UUID.randomUUID().toString(), 105L, 1L, 29_000L);

        paymentService.cancelBillingAndRefund(105L);

        assertThat(paymentService.findBySubscription(105L).get(0).getStatus())
                .isEqualTo(PaymentStatus.REFUNDED);
        assertThat(outboxRepository.findAll())
                .anyMatch(m -> m.getEventType().equals("PaymentRefunded")
                        && m.getPayload().contains("\"subscriptionId\":105"));
    }

    @Test
    @DisplayName("정기 결제 이벤트에 회차가 실린다")
    void scheduledPaymentEventCarriesCycle() {
        paymentService.processInitialPayment(UUID.randomUUID().toString(), 106L, 1L, 29_000L);
        paymentService.processScheduledPayment(billingScheduleRepository.findById(106L).orElseThrow());

        assertThat(outboxRepository.findAll())
                .anyMatch(m -> m.getEventType().equals("PaymentCompleted")
                        && m.getPayload().contains("\"subscriptionId\":106")
                        && m.getPayload().contains("\"billingCycle\":2"));
    }

    /** 회차 2를 가리키는 오래된 스케줄 사본 — 다중 인스턴스 레이스를 재현한다. */
    private BillingSchedule staleCopyOfCycle2(Long subscriptionId) {
        BillingSchedule stale = BillingSchedule.startAfterFirstPayment(
                subscriptionId, 1L, 29_000L, java.time.Duration.ofDays(30));
        return stale;
    }
}
