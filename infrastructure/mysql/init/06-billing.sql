-- 정기 결제 (D-25 ~ D-27)

-- payment 테이블에 회차를 추가한다.
-- 기존 멱등키(이벤트 UUID)는 "같은 이벤트의 재전송"을 막고,
-- (subscription_id, billing_cycle)은 "같은 회차의 다른 시도"를 막는다.
-- 스케줄러가 두 인스턴스에서 동시에 돌아도 회차당 한 건만 남는다.
ALTER TABLE payment_db.payment
    ADD COLUMN billing_cycle INT NOT NULL DEFAULT 1;

ALTER TABLE payment_db.payment
    ADD CONSTRAINT uk_payment_subscription_cycle UNIQUE (subscription_id, billing_cycle);

-- 결제 스케줄. payment-service가 소유한다(D-25).
-- 구독 쪽에 두면 payment가 매번 되물어야 해 동기 호출이 생긴다.
CREATE TABLE IF NOT EXISTS payment_db.billing_schedule (
    subscription_id   BIGINT      NOT NULL,
    member_id         BIGINT      NOT NULL,
    amount            BIGINT      NOT NULL,
    next_billing_cycle INT        NOT NULL,
    next_billing_at   DATETIME(6) NOT NULL,
    active            BOOLEAN     NOT NULL DEFAULT TRUE,
    PRIMARY KEY (subscription_id),
    -- 스케줄러가 "지금 청구할 대상"만 훑는 경로
    KEY idx_billing_due (active, next_billing_at)
) ENGINE = InnoDB;
