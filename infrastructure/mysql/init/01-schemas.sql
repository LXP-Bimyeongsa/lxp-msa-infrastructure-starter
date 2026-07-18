-- DB per service (스키마 단위)
--
-- 개발 단계에서는 MySQL 컨테이너 하나에 서비스별 스키마를 두고,
-- "타 서비스 스키마 접근 금지"라는 규율로 경계를 지킨다. (docs/DECISIONS.md D-09)
-- 운영 확장 시에는 이 스키마들을 서비스별 인스턴스로 분리한다.
--
-- course-service는 MongoDB를 쓰므로 여기에 없다. (D-08)

CREATE DATABASE IF NOT EXISTS member_db
    DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
CREATE DATABASE IF NOT EXISTS subscription_db
    DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
CREATE DATABASE IF NOT EXISTS payment_db
    DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;

-- 서비스별 전용 계정.
-- 각 계정은 자기 스키마에만 권한을 가지므로, 타 서비스 스키마 접근은
-- 규율이 아니라 DB 권한 수준에서 막힌다.
CREATE USER IF NOT EXISTS 'member'@'%' IDENTIFIED BY 'member';
CREATE USER IF NOT EXISTS 'subscription'@'%' IDENTIFIED BY 'subscription';
CREATE USER IF NOT EXISTS 'payment'@'%' IDENTIFIED BY 'payment';

GRANT ALL PRIVILEGES ON member_db.* TO 'member'@'%';
GRANT ALL PRIVILEGES ON subscription_db.* TO 'subscription'@'%';
GRANT ALL PRIVILEGES ON payment_db.* TO 'payment'@'%';

FLUSH PRIVILEGES;
