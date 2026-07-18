package com.lcs.common.outbox;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.Instant;
import java.util.UUID;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

// 도메인 변경과 같은 트랜잭션으로 커밋되는 발행 대기 이벤트. (docs/CONVENTIONS.md Outbox 규칙)
@Entity
@Table(name = "outbox")
public class OutboxMessage {

    @Id
    @Column(columnDefinition = "BINARY(16)")
    private UUID id;

    @Column(name = "aggregate_type", nullable = false, length = 100)
    private String aggregateType;

    @Column(name = "aggregate_id", nullable = false, length = 100)
    private String aggregateId;

    @Column(name = "event_type", nullable = false, length = 100)
    private String eventType;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(nullable = false)
    private String payload;

    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt;

    @Column(name = "published_at")
    private Instant publishedAt;

    protected OutboxMessage() {
        // JPA 전용
    }

    private OutboxMessage(String aggregateType, String aggregateId, String eventType, String payload) {
        this.id = UUID.randomUUID();
        this.aggregateType = aggregateType;
        this.aggregateId = aggregateId;
        this.eventType = eventType;
        this.payload = payload;
        this.createdAt = Instant.now();
    }

    public static OutboxMessage of(String aggregateType, String aggregateId, String eventType, String payload) {
        return new OutboxMessage(aggregateType, aggregateId, eventType, payload);
    }

    public void markPublished() {
        this.publishedAt = Instant.now();
    }

    public UUID getId() {
        return id;
    }

    public String getEventType() {
        return eventType;
    }

    public String getPayload() {
        return payload;
    }

    public Instant getPublishedAt() {
        return publishedAt;
    }

    /**
     * 라우팅 키 규칙: 이벤트명은 {Aggregate}{과거형동사} 2단어로 짓는다(CONVENTIONS.md).
     * SubscriptionCreated -> subscription.created
     */
    public String routingKey() {
        return eventType.replaceAll("([a-z])([A-Z])", "$1.$2").toLowerCase();
    }
}
