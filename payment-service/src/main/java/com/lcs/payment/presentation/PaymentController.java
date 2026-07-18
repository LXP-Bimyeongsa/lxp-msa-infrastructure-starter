package com.lcs.payment.presentation;

import com.lcs.payment.application.PaymentService;
import com.lcs.payment.domain.Payment;
import java.util.List;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/payments")
public class PaymentController {

    private final PaymentService paymentService;

    public PaymentController(PaymentService paymentService) {
        this.paymentService = paymentService;
    }

    @GetMapping("/subscriptions/{subscriptionId}")
    public List<PaymentResponse> findBySubscription(@PathVariable Long subscriptionId) {
        return paymentService.findBySubscription(subscriptionId).stream()
                .map(PaymentResponse::from)
                .toList();
    }

    public record PaymentResponse(
            Long paymentId,
            Long subscriptionId,
            Long memberId,
            Long amount,
            String status
    ) {
        static PaymentResponse from(Payment payment) {
            return new PaymentResponse(
                    payment.getId(),
                    payment.getSubscriptionId(),
                    payment.getMemberId(),
                    payment.getAmount(),
                    payment.getStatus().name()
            );
        }
    }
}
