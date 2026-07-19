-- 정기 결제 재시도(dunning) (D-37)
--
-- 이번 회차에서 실패한 횟수. 성공하면 0으로 돌아간다.
-- 스케줄에 두는 이유 — 재시도는 "이 구독의 이번 회차" 상태지 결제 건의 속성이 아니다.
--
-- 기존 행에는 0이 들어간다. 재시도를 한 번도 하지 않은 상태와 같으므로
-- 이미 돌고 있는 스케줄에 영향이 없다.
ALTER TABLE payment_db.billing_schedule
    ADD COLUMN retry_count INT NOT NULL DEFAULT 0;
