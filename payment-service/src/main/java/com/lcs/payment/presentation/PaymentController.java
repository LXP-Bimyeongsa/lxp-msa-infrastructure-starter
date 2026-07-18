package com.lcs.payment.presentation;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/payments")
public class PaymentController {

    @GetMapping("/subscriptions/{subscriptionId}")
    public PaymentResponse findBySubscription(@PathVariable Long subscriptionId) {
        return new PaymentResponse(
                10_000L + subscriptionId,
                subscriptionId,
                29_000L,
                "APPROVED"
        );
    }

    public record PaymentResponse(
            Long paymentId,
            Long subscriptionId,
            Long amount,
            String status
    ) {
    }
}
