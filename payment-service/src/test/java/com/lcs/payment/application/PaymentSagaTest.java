package com.lcs.payment.application;

import static org.assertj.core.api.Assertions.assertThat;

import com.lcs.payment.domain.Payment;
import com.lcs.payment.domain.PaymentStatus;
import com.lcs.payment.infrastructure.outbox.OutboxRepository;
import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;

@SpringBootTest
@ActiveProfiles("test")
class PaymentSagaTest {

    @Autowired
    private PaymentService paymentService;

    @Autowired
    private OutboxRepository outboxRepository;

    @Test
    @DisplayName("결제 성공 시 APPROVED 저장 + PaymentCompleted 발행")
    void approvesAndEmitsCompleted() {
        String eventId = UUID.randomUUID().toString();

        paymentService.processInitialPayment(eventId, 10L, 1L, 29_000L);

        List<Payment> payments = paymentService.findBySubscription(10L);
        assertThat(payments).hasSize(1);
        assertThat(payments.get(0).getStatus()).isEqualTo(PaymentStatus.APPROVED);
        assertThat(outboxRepository.findAll())
                .anyMatch(m -> m.getEventType().equals("PaymentCompleted"));
    }

    @Test
    @DisplayName("같은 이벤트가 두 번 와도 결제는 한 건이다 — 멱등키")
    void duplicateEventProcessedOnce() {
        String eventId = UUID.randomUUID().toString();

        paymentService.processInitialPayment(eventId, 11L, 1L, 29_000L);
        paymentService.processInitialPayment(eventId, 11L, 1L, 29_000L); // at-least-once 재전송

        assertThat(paymentService.findBySubscription(11L)).hasSize(1);
        // 발행 이벤트도 한 건이어야 한다
        long completedCount = outboxRepository.findAll().stream()
                .filter(m -> m.getEventType().equals("PaymentCompleted"))
                .filter(m -> m.getPayload().contains("\"subscriptionId\":11"))
                .count();
        assertThat(completedCount).isEqualTo(1);
    }

    @Test
    @DisplayName("금액이 0 이하면 FAILED 저장 + PaymentFailed 발행")
    void invalidAmountFails() {
        paymentService.processInitialPayment(UUID.randomUUID().toString(), 12L, 1L, 0L);

        assertThat(paymentService.findBySubscription(12L).get(0).getStatus())
                .isEqualTo(PaymentStatus.FAILED);
        assertThat(outboxRepository.findAll())
                .anyMatch(m -> m.getEventType().equals("PaymentFailed"));
    }

    @Test
    @DisplayName("해지 이벤트를 받으면 승인 결제를 환불하고 PaymentRefunded를 발행한다 (D-16)")
    void refundOnCancellation() {
        paymentService.processInitialPayment(UUID.randomUUID().toString(), 13L, 1L, 29_000L);

        paymentService.cancelBillingAndRefund(13L);

        assertThat(paymentService.findBySubscription(13L).get(0).getStatus())
                .isEqualTo(PaymentStatus.REFUNDED);
        assertThat(outboxRepository.findAll())
                .anyMatch(m -> m.getEventType().equals("PaymentRefunded")
                        && m.routingKey().equals("payment.refunded"));
    }

    @Test
    @DisplayName("환불도 멱등이다 — 해지 이벤트가 두 번 와도 환불 이벤트는 한 건")
    void refundIsIdempotent() {
        paymentService.processInitialPayment(UUID.randomUUID().toString(), 14L, 1L, 29_000L);

        paymentService.cancelBillingAndRefund(14L);
        paymentService.cancelBillingAndRefund(14L); // 재전송

        long refundedCount = outboxRepository.findAll().stream()
                .filter(m -> m.getEventType().equals("PaymentRefunded"))
                .filter(m -> m.getPayload().contains("\"subscriptionId\":14"))
                .count();
        assertThat(refundedCount).isEqualTo(1);
    }

    @Test
    @DisplayName("결제가 없는 구독의 해지는 환불 없이 조용히 끝난다")
    void refundWithoutPaymentIsNoop() {
        long before = outboxRepository.count();

        paymentService.cancelBillingAndRefund(999L);

        assertThat(outboxRepository.count()).isEqualTo(before);
    }
}
