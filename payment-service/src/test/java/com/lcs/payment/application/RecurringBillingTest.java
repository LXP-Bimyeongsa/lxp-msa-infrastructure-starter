package com.lcs.payment.application;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.BDDMockito.given;

import com.lcs.common.outbox.OutboxRepository;
import com.lcs.payment.domain.BillingSchedule;
import com.lcs.payment.domain.PaymentStatus;
import com.lcs.payment.infrastructure.persistence.BillingScheduleRepository;
import java.util.UUID;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.util.ReflectionTestUtils;

@SpringBootTest
@ActiveProfiles("test")
class RecurringBillingTest {

    @Autowired
    private PaymentService paymentService;

    @Autowired
    private BillingScheduleRepository billingScheduleRepository;

    @Autowired
    private OutboxRepository outboxRepository;

    // PG는 외부 시스템이라 모킹한다 (D-39).
    @MockitoBean
    private PaymentGateway paymentGateway;

    @BeforeEach
    void stubPaymentGateway() {
        // 금액 0 = 거절(재시도 가능). dunning 테스트가 이 전제를 쓴다.
        given(paymentGateway.approve(anyString(), anyLong(), anyString()))
                .willAnswer(invocation -> {
                    long amount = invocation.getArgument(1);
                    return amount > 0
                            ? PgApproval.approved("pg-tx-" + UUID.randomUUID())
                            : PgApproval.declined("INVALID_AMOUNT", true);
                });
    }

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

    @Test
    @DisplayName("정기 결제가 실패해도 바로 끊지 않고 재시도를 예약한다 (D-37)")
    void failedScheduledPaymentSchedulesRetry() {
        BillingSchedule schedule = givenFailingSchedule(110L);

        paymentService.processScheduledPayment(schedule);

        BillingSchedule after = billingScheduleRepository.findById(110L).orElseThrow();
        assertThat(after.isActive()).isTrue();          // 아직 살아 있다
        assertThat(after.getRetryCount()).isEqualTo(1);
        assertThat(after.getNextBillingCycle()).isEqualTo(2);   // 회차는 그대로
    }

    @Test
    @DisplayName("재시도가 남아 있는 동안에는 PaymentFailed를 발행하지 않는다 (D-37)")
    void retryingDoesNotEmitPaymentFailed() {
        BillingSchedule schedule = givenFailingSchedule(111L);

        paymentService.processScheduledPayment(schedule);

        // 발행하면 subscription이 받아서 해지해버린다 — 재시도의 의미가 없어진다.
        assertThat(outboxRepository.findAll())
                .noneMatch(m -> m.getEventType().equals("PaymentFailed")
                        && m.getPayload().contains("\"subscriptionId\":111"));
    }

    @Test
    @DisplayName("재시도를 다 쓰면 스케줄이 멈추고 PaymentFailed가 발행된다 (D-37)")
    void exhaustedRetriesStopScheduleAndEmitFailure() {
        BillingSchedule schedule = givenFailingSchedule(112L);

        // 기본 정책은 3회. 3번째 시도에서 포기한다.
        for (int i = 0; i < 3; i++) {
            paymentService.processScheduledPayment(
                    billingScheduleRepository.findById(112L).orElseThrow());
        }

        BillingSchedule after = billingScheduleRepository.findById(112L).orElseThrow();
        assertThat(after.isActive()).isFalse();
        assertThat(outboxRepository.findAll())
                .anyMatch(m -> m.getEventType().equals("PaymentFailed")
                        && m.getPayload().contains("\"subscriptionId\":112"));
    }

    @Test
    @DisplayName("재시도 도중 성공하면 회차가 올라가고 실패 횟수가 초기화된다 (D-37)")
    void successDuringRetryResetsCount() {
        BillingSchedule schedule = givenFailingSchedule(113L);
        paymentService.processScheduledPayment(schedule);
        assertThat(billingScheduleRepository.findById(113L).orElseThrow().getRetryCount()).isEqualTo(1);

        // 카드가 풀린 상황 — 같은 스케줄을 정상 금액으로 바꿔 다시 시도한다.
        BillingSchedule recovered = billingScheduleRepository.findById(113L).orElseThrow();
        ReflectionTestUtils.setField(recovered, "amount", 29_000L);
        paymentService.processScheduledPayment(recovered);

        BillingSchedule after = billingScheduleRepository.findById(113L).orElseThrow();
        assertThat(after.getRetryCount()).isZero();
        assertThat(after.getNextBillingCycle()).isEqualTo(3);
    }

    @Test
    @DisplayName("최초 결제 실패는 재시도하지 않는다 — 즉시 PaymentFailed (D-37)")
    void firstPaymentFailureIsTerminal() {
        paymentService.processInitialPayment(UUID.randomUUID().toString(), 114L, 1L, 0L);

        // 아직 아무것도 제공하지 않은 상태라 유예할 이유가 없다.
        assertThat(billingScheduleRepository.findById(114L)).isEmpty();
        assertThat(outboxRepository.findAll())
                .anyMatch(m -> m.getEventType().equals("PaymentFailed")
                        && m.getPayload().contains("\"subscriptionId\":114"));
    }

    @Test
    @DisplayName("재시도 불가 거절(도난 카드)은 dunning을 돌리지 않고 즉시 중단한다 (D-39)")
    void nonRetryableDeclineStopsImmediately() {
        given(paymentGateway.approve(anyString(), anyLong(), anyString()))
                .willReturn(PgApproval.declined("STOLEN_CARD", false));
        BillingSchedule schedule = givenFailingSchedule(120L);

        paymentService.processScheduledPayment(schedule);

        // 3일씩 3번 더 긁어봐야 같은 답이 온다. 첫 실패에서 끝낸다.
        BillingSchedule after = billingScheduleRepository.findById(120L).orElseThrow();
        assertThat(after.isActive()).isFalse();
        assertThat(after.getRetryCount()).isZero();
    }

    @Test
    @DisplayName("재시도 불가 거절도 PaymentFailed를 발행한다 — 구독이 해지돼야 하므로 (D-39)")
    void nonRetryableDeclineEmitsPaymentFailed() {
        given(paymentGateway.approve(anyString(), anyLong(), anyString()))
                .willReturn(PgApproval.declined("STOLEN_CARD", false));
        BillingSchedule schedule = givenFailingSchedule(121L);

        paymentService.processScheduledPayment(schedule);

        assertThat(outboxRepository.findAll())
                .anyMatch(m -> m.getEventType().equals("PaymentFailed")
                        && m.getPayload().contains("\"subscriptionId\":121")
                        && m.getPayload().contains("STOLEN_CARD"));
    }

    @Test
    @DisplayName("PG 통신 실패는 재시도 대상이다 — 승인됐는지 모르는 상태라 단정하지 않는다 (D-39)")
    void pgUnreachableIsRetried() {
        given(paymentGateway.approve(anyString(), anyLong(), anyString()))
                .willReturn(PgApproval.unreachable());
        BillingSchedule schedule = givenFailingSchedule(122L);

        paymentService.processScheduledPayment(schedule);

        BillingSchedule after = billingScheduleRepository.findById(122L).orElseThrow();
        assertThat(after.isActive()).isTrue();
        assertThat(after.getRetryCount()).isEqualTo(1);
    }

    @Test
    @DisplayName("승인 시 PG 거래 ID를 저장한다 — 없으면 환불할 수 없다 (D-39)")
    void storesPgTransactionId() {
        given(paymentGateway.approve(anyString(), anyLong(), anyString()))
                .willReturn(PgApproval.approved("pg-tx-fixed"));

        paymentService.processInitialPayment(UUID.randomUUID().toString(), 123L, 1L, 29_000L);

        assertThat(paymentService.findBySubscription(123L).get(0).getPgTransactionId())
                .isEqualTo("pg-tx-fixed");
    }

    /** 승인되지 않는 금액(0)으로 활성 스케줄을 만든다 — 정기 결제 실패를 재현한다. */
    private BillingSchedule givenFailingSchedule(Long subscriptionId) {
        return billingScheduleRepository.save(BillingSchedule.startAfterFirstPayment(
                subscriptionId, 1L, 0L, java.time.Duration.ofDays(30)));
    }

    /** 회차 2를 가리키는 오래된 스케줄 사본 — 다중 인스턴스 레이스를 재현한다. */
    private BillingSchedule staleCopyOfCycle2(Long subscriptionId) {
        BillingSchedule stale = BillingSchedule.startAfterFirstPayment(
                subscriptionId, 1L, 29_000L, java.time.Duration.ofDays(30));
        return stale;
    }
}
