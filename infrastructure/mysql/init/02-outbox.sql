-- Outbox 테이블
--
-- 도메인 변경과 이벤트 기록을 하나의 로컬 트랜잭션으로 커밋하기 위한 테이블.
-- 각 서비스가 자기 스키마에 자기 outbox를 소유한다. (docs/CONVENTIONS.md)
--
-- 서비스 내부 @Scheduled 릴레이가 published_at IS NULL 인 행을 폴링해
-- RabbitMQ에 발행하고, publisher confirm 수신 후 published_at을 채운다.

CREATE TABLE IF NOT EXISTS subscription_db.outbox (
    id             BINARY(16)   NOT NULL,
    aggregate_type VARCHAR(100) NOT NULL,
    aggregate_id   VARCHAR(100) NOT NULL,
    event_type     VARCHAR(100) NOT NULL,
    payload        JSON         NOT NULL,
    created_at     DATETIME(6)  NOT NULL,
    published_at   DATETIME(6)  NULL,
    PRIMARY KEY (id),
    -- 릴레이가 미발행 행만 시간순으로 훑는 경로.
    KEY idx_outbox_unpublished (published_at, created_at)
) ENGINE = InnoDB;

CREATE TABLE IF NOT EXISTS payment_db.outbox (
    id             BINARY(16)   NOT NULL,
    aggregate_type VARCHAR(100) NOT NULL,
    aggregate_id   VARCHAR(100) NOT NULL,
    event_type     VARCHAR(100) NOT NULL,
    payload        JSON         NOT NULL,
    created_at     DATETIME(6)  NOT NULL,
    published_at   DATETIME(6)  NULL,
    PRIMARY KEY (id),
    KEY idx_outbox_unpublished (published_at, created_at)
) ENGINE = InnoDB;

CREATE TABLE IF NOT EXISTS member_db.outbox (
    id             BINARY(16)   NOT NULL,
    aggregate_type VARCHAR(100) NOT NULL,
    aggregate_id   VARCHAR(100) NOT NULL,
    event_type     VARCHAR(100) NOT NULL,
    payload        JSON         NOT NULL,
    created_at     DATETIME(6)  NOT NULL,
    published_at   DATETIME(6)  NULL,
    PRIMARY KEY (id),
    KEY idx_outbox_unpublished (published_at, created_at)
) ENGINE = InnoDB;
