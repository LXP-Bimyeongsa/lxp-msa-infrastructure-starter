-- payment-service 도메인 테이블
-- 스키마 소유권은 이 SQL에 있다. 애플리케이션은 ddl-auto: validate.

CREATE TABLE IF NOT EXISTS payment_db.payment (
    id              BIGINT       NOT NULL AUTO_INCREMENT,
    subscription_id BIGINT       NOT NULL,
    member_id       BIGINT       NOT NULL,
    amount          BIGINT       NOT NULL,
    status          VARCHAR(20)  NOT NULL,
    -- 사가 이벤트는 at-least-once라 같은 결제 요청이 두 번 올 수 있다.
    -- 이벤트 id(outbox UUID)를 멱등키로 삼아 중복 결제를 DB 수준에서 차단한다.
    idempotency_key VARCHAR(36)  NOT NULL,
    created_at      DATETIME(6)  NOT NULL,
    refunded_at     DATETIME(6)  NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_payment_idempotency (idempotency_key),
    KEY idx_payment_subscription (subscription_id)
) ENGINE = InnoDB;
