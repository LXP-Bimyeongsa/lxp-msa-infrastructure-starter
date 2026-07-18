-- subscription-service 도메인 테이블
-- 스키마 소유권은 이 SQL에 있다. 애플리케이션은 ddl-auto: validate.

CREATE TABLE IF NOT EXISTS subscription_db.subscription (
    id           BIGINT      NOT NULL AUTO_INCREMENT,
    member_id    BIGINT      NOT NULL,
    plan         VARCHAR(20) NOT NULL,
    status       VARCHAR(20) NOT NULL,
    amount       BIGINT      NOT NULL,
    created_at   DATETIME(6) NOT NULL,
    activated_at DATETIME(6) NULL,
    cancelled_at DATETIME(6) NULL,
    PRIMARY KEY (id),
    -- 회원별 구독 조회 경로 (회원탈퇴 사가에서 활성 구독 일괄 해지에 사용)
    KEY idx_subscription_member (member_id, status)
) ENGINE = InnoDB;
