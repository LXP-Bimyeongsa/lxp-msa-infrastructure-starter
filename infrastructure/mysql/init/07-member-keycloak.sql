-- Keycloak 이관 (D-20)
--
-- 자격증명은 Keycloak이 소유한다. member_db는 도메인 프로필만 갖는다.
-- 비밀번호를 두 곳에 두면 어느 쪽이 진짜인지 알 수 없고,
-- 변경 시 반드시 어긋난다.
ALTER TABLE member_db.member DROP COLUMN password_hash;

-- Keycloak sub. 어느 Keycloak 계정과 연결된 프로필인지 추적하기 위해 남긴다.
ALTER TABLE member_db.member
    ADD COLUMN keycloak_id VARCHAR(36) NULL,
    ADD UNIQUE KEY uk_member_keycloak_id (keycloak_id);
