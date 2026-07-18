package com.lcs.subscription.infrastructure.messaging;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.lcs.subscription.application.SubscriptionService;
import org.springframework.amqp.rabbit.annotation.RabbitListener;
import org.springframework.stereotype.Component;

// 회원탈퇴 이벤트 소비 (D-31). at-least-once 전제이므로 처리가 멱등이어야 한다 —
// onMemberWithdrawn()이 이미 CANCELLED인 구독을 건너뛰는 방식으로 멱등을 보장한다.
@Component
public class MemberWithdrawnListener {

    private final SubscriptionService subscriptionService;
    private final ObjectMapper objectMapper;

    public MemberWithdrawnListener(SubscriptionService subscriptionService, ObjectMapper objectMapper) {
        this.subscriptionService = subscriptionService;
        this.objectMapper = objectMapper;
    }

    @RabbitListener(queues = "subscription.member-withdrawn")
    public void handle(String message) throws Exception {
        JsonNode payload = objectMapper.readTree(message);
        subscriptionService.onMemberWithdrawn(payload.get("memberId").asLong());
    }
}
