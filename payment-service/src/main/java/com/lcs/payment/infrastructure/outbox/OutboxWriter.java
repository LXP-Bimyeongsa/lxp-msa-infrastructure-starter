package com.lcs.payment.infrastructure.outbox;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.stereotype.Component;

// 도메인 트랜잭션 안에서 호출한다 — 비즈니스 저장과 outbox INSERT가 함께 커밋되거나 함께 롤백된다.
@Component
public class OutboxWriter {

    private final OutboxRepository outboxRepository;
    private final ObjectMapper objectMapper;

    public OutboxWriter(OutboxRepository outboxRepository, ObjectMapper objectMapper) {
        this.outboxRepository = outboxRepository;
        this.objectMapper = objectMapper;
    }

    public void write(String aggregateType, String aggregateId, String eventType, Object payload) {
        try {
            String json = objectMapper.writeValueAsString(payload);
            outboxRepository.save(OutboxMessage.of(aggregateType, aggregateId, eventType, json));
        } catch (JsonProcessingException e) {
            // 직렬화 실패는 코드 버그다. 트랜잭션을 롤백시켜 도메인 변경도 함께 취소한다.
            throw new IllegalStateException("outbox payload 직렬화 실패: " + eventType, e);
        }
    }
}
