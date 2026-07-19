-- PG 연동 (D-39)
--
-- pg_transaction_id: PG 승인번호. 환불할 때 PG에 넘겨야 한다.
--   이것이 없으면 우리 DB에서 상태만 REFUNDED로 바꿀 수 있을 뿐
--   실제 돈은 돌려주지 못한다. 실패한 결제는 승인번호가 없으므로 NULL 허용.
--
-- pg_decline_code: 거절 사유. 남기지 않으면 "왜 결제가 안 됐나" 문의에 답할 수 없다.
ALTER TABLE payment_db.payment
    ADD COLUMN pg_transaction_id VARCHAR(64) NULL,
    ADD COLUMN pg_decline_code   VARCHAR(40) NULL;
