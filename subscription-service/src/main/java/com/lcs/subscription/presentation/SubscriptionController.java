package com.lcs.subscription.presentation;

import com.lcs.subscription.application.SubscriptionService;
import com.lcs.subscription.domain.Subscription;
import com.lcs.subscription.domain.SubscriptionPlan;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotNull;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/subscriptions")
public class SubscriptionController {

    private final SubscriptionService subscriptionService;

    public SubscriptionController(SubscriptionService subscriptionService) {
        this.subscriptionService = subscriptionService;
    }

    // memberId는 body가 아니라 gateway가 JWT에서 추출해 넣는 X-Member-Id 헤더에서 받는다.
    // body로 받으면 남의 memberId로 구독을 만들 수 있다.
    @PostMapping
    public ResponseEntity<SubscriptionResponse> subscribe(
            @RequestHeader("X-Member-Id") Long memberId,
            @Valid @RequestBody SubscribeRequest request) {
        Subscription subscription = subscriptionService.subscribe(memberId, request.plan());
        return ResponseEntity.status(HttpStatus.CREATED).body(SubscriptionResponse.from(subscription));
    }

    @GetMapping("/{subscriptionId}")
    public SubscriptionResponse find(@PathVariable Long subscriptionId) {
        return SubscriptionResponse.from(subscriptionService.findById(subscriptionId));
    }

    @DeleteMapping("/{subscriptionId}")
    public SubscriptionResponse cancel(
            @RequestHeader("X-Member-Id") Long memberId,
            @PathVariable Long subscriptionId) {
        return SubscriptionResponse.from(subscriptionService.cancel(subscriptionId, memberId));
    }

    public record SubscribeRequest(@NotNull SubscriptionPlan plan) {
    }

    public record SubscriptionResponse(
            Long subscriptionId,
            Long memberId,
            String plan,
            Long amount,
            String status
    ) {
        static SubscriptionResponse from(Subscription subscription) {
            return new SubscriptionResponse(
                    subscription.getId(),
                    subscription.getMemberId(),
                    subscription.getPlan().name(),
                    subscription.getAmount(),
                    subscription.getStatus().name()
            );
        }
    }
}
