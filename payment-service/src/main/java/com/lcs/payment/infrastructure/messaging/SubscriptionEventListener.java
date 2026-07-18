package com.lcs.payment.infrastructure.messaging;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.lcs.payment.application.PaymentService;
import org.springframework.amqp.rabbit.annotation.RabbitListener;
import org.springframework.amqp.support.AmqpHeaders;
import org.springframework.messaging.handler.annotation.Header;
import org.springframework.stereotype.Component;

@Component
public class SubscriptionEventListener {

    private final PaymentService paymentService;
    private final ObjectMapper objectMapper;

    public SubscriptionEventListener(PaymentService paymentService, ObjectMapper objectMapper) {
        this.paymentService = paymentService;
        this.objectMapper = objectMapper;
    }

    // 이벤트에 결제에 필요한 데이터가 전부 실려 온다(event-carried state transfer, D-17).
    // subscription을 동기로 되묻지 않는다.
    @RabbitListener(queues = "payment.subscription-created")
    public void onSubscriptionCreated(String message,
                                      @Header(AmqpHeaders.MESSAGE_ID) String messageId) throws Exception {
        JsonNode payload = objectMapper.readTree(message);
        paymentService.processPayment(
                messageId,
                payload.get("subscriptionId").asLong(),
                payload.get("memberId").asLong(),
                payload.get("amount").asLong()
        );
    }

    @RabbitListener(queues = "payment.subscription-cancelled")
    public void onSubscriptionCancelled(String message) throws Exception {
        JsonNode payload = objectMapper.readTree(message);
        paymentService.refund(payload.get("subscriptionId").asLong());
    }
}
