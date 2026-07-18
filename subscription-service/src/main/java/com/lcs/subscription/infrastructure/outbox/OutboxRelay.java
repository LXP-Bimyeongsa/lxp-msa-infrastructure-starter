package com.lcs.subscription.infrastructure.outbox;

import java.util.List;
import java.util.concurrent.TimeUnit;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.amqp.rabbit.connection.CorrelationData;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

// 서비스 내부 릴레이(D-11). 미발행 outbox를 폴링해 RabbitMQ로 발행하고,
// publisher confirm을 받은 뒤에만 발행 완료로 마킹한다.
// confirm 전에 프로세스가 죽으면 재발행된다 — 그래서 소비자는 멱등해야 한다(at-least-once).
@Component
@ConditionalOnProperty(name = "outbox.relay.enabled", havingValue = "true", matchIfMissing = true)
public class OutboxRelay {

    private static final Logger log = LoggerFactory.getLogger(OutboxRelay.class);

    private final OutboxRepository outboxRepository;
    private final RabbitTemplate rabbitTemplate;
    private final String exchange;

    public OutboxRelay(OutboxRepository outboxRepository,
                       RabbitTemplate rabbitTemplate,
                       @Value("${outbox.relay.exchange}") String exchange) {
        this.outboxRepository = outboxRepository;
        this.rabbitTemplate = rabbitTemplate;
        this.exchange = exchange;
    }

    @Scheduled(fixedDelayString = "${outbox.relay.poll-interval-ms:1000}")
    @Transactional
    public void relay() {
        List<OutboxMessage> pending = outboxRepository.findTop100ByPublishedAtIsNullOrderByCreatedAtAsc();
        for (OutboxMessage message : pending) {
            try {
                String eventId = message.getId().toString();
                CorrelationData correlation = new CorrelationData(eventId);
                // messageId에 outbox UUID를 싣는다 — 소비자가 멱등키로 사용한다.
                rabbitTemplate.convertAndSend(exchange, message.routingKey(), message.getPayload(),
                        m -> {
                            m.getMessageProperties().setMessageId(eventId);
                            return m;
                        },
                        correlation);
                CorrelationData.Confirm confirm = correlation.getFuture().get(5, TimeUnit.SECONDS);
                if (confirm != null && confirm.isAck()) {
                    message.markPublished();
                } else {
                    // nack — 브로커가 거부. 다음 폴링에서 재시도한다.
                    log.warn("outbox 발행 nack: id={} type={}", message.getId(), message.getEventType());
                }
            } catch (Exception e) {
                // 발행 실패 시 마킹하지 않고 다음 폴링에서 재시도. 순서 보존을 위해 이번 배치는 중단.
                log.warn("outbox 발행 실패, 재시도 예정: id={} type={} cause={}",
                        message.getId(), message.getEventType(), e.getMessage());
                break;
            }
        }
    }
}
