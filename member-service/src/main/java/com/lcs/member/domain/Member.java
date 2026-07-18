package com.lcs.member.domain;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.Instant;

@Entity
@Table(name = "member")
public class Member {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, unique = true, length = 320)
    private String email;

    // 자격증명은 Keycloak이 소유한다 (D-20). 여기엔 연결 식별자만 둔다.
    // 비밀번호를 두 곳에 두면 변경 시 반드시 어긋난다.
    @Column(name = "keycloak_id", unique = true, length = 36)
    private String keycloakId;

    @Column(nullable = false, length = 50)
    private String name;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 20)
    private MemberStatus status;

    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt;

    protected Member() {
        // JPA 전용
    }

    private Member(String email, String name) {
        this.email = email;
        this.name = name;
        this.status = MemberStatus.ACTIVE;
        this.createdAt = Instant.now();
    }

    public static Member register(String email, String name) {
        return new Member(email, name);
    }

    /** Keycloak 사용자 생성 후 연결한다. */
    public void linkKeycloakUser(String keycloakId) {
        this.keycloakId = keycloakId;
    }

    public void withdraw() {
        this.status = MemberStatus.WITHDRAWN;
    }

    public boolean isActive() {
        return this.status == MemberStatus.ACTIVE;
    }

    public Long getId() {
        return id;
    }

    public String getEmail() {
        return email;
    }

    public String getKeycloakId() {
        return keycloakId;
    }

    public String getName() {
        return name;
    }

    public MemberStatus getStatus() {
        return status;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }
}
