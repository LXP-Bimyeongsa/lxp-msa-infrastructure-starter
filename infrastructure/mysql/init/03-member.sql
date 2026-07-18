-- member-service 도메인 테이블
--
-- 스키마 소유권은 이 SQL에 있다. 애플리케이션은 ddl-auto: validate 로 동작하며
-- 여기 정의와 엔티티가 어긋나면 기동 시점에 실패한다. 런타임에 조용히
-- 어긋나는 것보다 기동이 깨지는 편이 낫다.

CREATE TABLE IF NOT EXISTS member_db.member (
    id            BIGINT       NOT NULL AUTO_INCREMENT,
    email         VARCHAR(320) NOT NULL,
    password_hash VARCHAR(100) NOT NULL,
    name          VARCHAR(50)  NOT NULL,
    status        VARCHAR(20)  NOT NULL,
    created_at    DATETIME(6)  NOT NULL,
    PRIMARY KEY (id),
    -- 애플리케이션 선검사만으로는 동시 가입 요청을 막을 수 없다.
    UNIQUE KEY uk_member_email (email)
) ENGINE = InnoDB;
