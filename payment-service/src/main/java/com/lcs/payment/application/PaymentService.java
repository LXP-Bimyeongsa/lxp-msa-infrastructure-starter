package com.lcs.payment.application;

import com.lcs.payment.domain.Payment;
import com.lcs.payment.infrastructure.outbox.OutboxWriter;
import com.lcs.payment.infrastructure.persistence.PaymentRepository;
import java.util.List;
import java.util.Map;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class PaymentService {

    private static final Logger log = LoggerFactory.getLogger(PaymentService.class);
    private static final String AGGREGATE = "Payment";

    private final PaymentRepository paymentRepository;
    private final OutboxWriter outboxWriter;

    public PaymentService(PaymentRepository paymentRepository, OutboxWriter outboxWriter) {
        this.paymentRepository = paymentRepository;
        this.outboxWriter = outboxWriter;
    }

    /**
     * SubscriptionCreated 소비 — 결제 수행.
     * 멱등키(eventId)로 중복 처리(at-least-once 재전송)를 차단한다.
     * PG 연동 전까지는 mock 결제다(P-01): 항상 승인, 금액이 0 이하일 때만 실패.
     */
    @Transactional
    public void processPayment(String eventId, Long subscriptionId, Long memberId, Long amount) {
        if (paymentRepository.findByIdempotencyKey(eventId).isPresent()) {
            log.info("이미 처리된 결제 이벤트, 무시: eventId={}", eventId);
            return;
        }

        boolean approved = amount != null && amount > 0;
        Payment payment = approved
                ? Payment.approved(subscriptionId, memberId, amount, eventId)
                : Payment.failed(subscriptionId, memberId, amount == null ? 0 : amount, eventId);

        try {
            paymentRepository.saveAndFlush(payment);
        } catch (DataIntegrityViolationException e) {
            // 동시 소비 레이스 — 다른 스레드가 먼저 처리했다. 멱등하므로 조용히 종료.
            log.info("동시 처리 감지, 무시: eventId={}", eventId);
            return;
        }

        if (approved) {
            outboxWriter.write(AGGREGATE, String.valueOf(payment.getId()), "PaymentCompleted", Map.of(
                    "paymentId", payment.getId(),
                    "subscriptionId", subscriptionId,
                    "memberId", memberId,
                    "amount", amount
            ));
        } else {
            outboxWriter.write(AGGREGATE, String.valueOf(payment.getId()), "PaymentFailed", Map.of(
                    "paymentId", payment.getId(),
                    "subscriptionId", subscriptionId,
                    "memberId", memberId,
                    "reason", "invalid amount"
            ));
        }
    }

    /**
     * SubscriptionCancelled 소비 — 환불(D-16).
     * 승인된 결제가 없으면(결제 전 해지, 이미 환불) 할 일이 없다 — 멱등.
     */
    @Transactional
    public void refund(Long subscriptionId) {
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
}
