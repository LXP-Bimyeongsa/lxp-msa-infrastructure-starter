package com.lcs.subscription.infrastructure.messaging;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.lcs.subscription.application.SubscriptionService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.amqp.rabbit.annotation.RabbitListener;
import org.springframework.amqp.support.AmqpHeaders;
import org.springframework.messaging.handler.annotation.Header;
import org.springframework.stereotype.Component;

// 결제 결과 이벤트 소비. at-least-once 전제이므로 처리 자체가 멱등이어야 한다 —
// activate()/cancel()이 상태를 확인하고 무시하는 방식으로 멱등을 보장한다.
@Component
public class PaymentResultListener {

    private static final Logger log = LoggerFactory.getLogger(PaymentResultListener.class);

    private final SubscriptionService subscriptionService;
    private final ObjectMapper objectMapper;

    public PaymentResultListener(SubscriptionService subscriptionService, ObjectMapper objectMapper) {
        this.subscriptionService = subscriptionService;
        this.objectMapper = objectMapper;
    }

    @RabbitListener(queues = "subscription.payment-result")
    public void handle(String message,
                       @Header(AmqpHeaders.RECEIVED_ROUTING_KEY) String routingKey) throws Exception {
        JsonNode payload = objectMapper.readTree(message);
        long subscriptionId = payload.get("subscriptionId").asLong();

        switch (routingKey) {
            case "payment.completed" -> subscriptionService.onPaymentCompleted(subscriptionId);
            case "payment.failed" -> subscriptionService.onPaymentFailed(
                    subscriptionId,
                    payload.path("reason").asText("unknown"));
            // 환불 완료는 정보성 — 구독은 이미 CANCELLED 상태다.
            case "payment.refunded" -> log.info("환불 완료 수신: subscriptionId={}", subscriptionId);
            default -> log.warn("알 수 없는 라우팅 키: {}", routingKey);
        }
    }
}
