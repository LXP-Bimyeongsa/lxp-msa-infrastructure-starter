package com.lcs.subscription.presentation;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

// payment-service를 subscription-service로 통합(임시). 추후 결제 도메인 분리 시 별도 서비스로 추출.
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
