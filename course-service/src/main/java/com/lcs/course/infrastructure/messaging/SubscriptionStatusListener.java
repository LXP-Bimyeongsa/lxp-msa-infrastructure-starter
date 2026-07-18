package com.lcs.course.infrastructure.messaging;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.lcs.course.application.EntitlementService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.amqp.rabbit.annotation.RabbitListener;
import org.springframework.amqp.support.AmqpHeaders;
import org.springframework.messaging.handler.annotation.Header;
import org.springframework.stereotype.Component;

// 구독 상태 이벤트를 소비해 재생 권한 읽기 모델을 갱신한다 (D-36).
// at-least-once 전제이므로 처리가 멱등해야 한다 —
// subscriptionId를 _id로 쓰는 upsert라 같은 이벤트가 두 번 와도 결과가 같다.
@Component
public class SubscriptionStatusListener {

    private static final Logger log = LoggerFactory.getLogger(SubscriptionStatusListener.class);

    private final EntitlementService entitlementService;
    private final ObjectMapper objectMapper;

    public SubscriptionStatusListener(EntitlementService entitlementService, ObjectMapper objectMapper) {
        this.entitlementService = entitlementService;
        this.objectMapper = objectMapper;
    }

    @RabbitListener(queues = "course.subscription-status")
    public void handle(String message,
                       @Header(AmqpHeaders.RECEIVED_ROUTING_KEY) String routingKey) throws Exception {
        JsonNode payload = objectMapper.readTree(message);
        String subscriptionId = payload.get("subscriptionId").asText();
        long memberId = payload.get("memberId").asLong();

        switch (routingKey) {
            case "subscription.activated" -> entitlementService.grant(subscriptionId, memberId);
            case "subscription.cancelled" -> entitlementService.revoke(subscriptionId, memberId);
            default -> log.warn("알 수 없는 라우팅 키: {}", routingKey);
        }
    }
}
