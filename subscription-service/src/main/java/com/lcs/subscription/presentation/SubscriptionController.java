package com.lcs.subscription.presentation;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/subscriptions")
public class SubscriptionController {

    @GetMapping("/{subscriptionId}")
    public SubscriptionResponse find(@PathVariable Long subscriptionId) {
        return new SubscriptionResponse(subscriptionId, 100L, "BASIC", "ACTIVE");
    }

    public record SubscriptionResponse(
            Long subscriptionId,
            Long memberId,
            String plan,
            String status
    ) {
    }
}
