package com.lcs.gateway.security;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpMethod;

class PublicPathsTest {

    @Test
    @DisplayName("인증 경로와 가입, ping은 공개다")
    void publicPaths() {
        assertThat(PublicPaths.isPublic(HttpMethod.POST, "/api/auth/login")).isTrue();
        assertThat(PublicPaths.isPublic(HttpMethod.GET, "/api/auth/ping")).isTrue();
        assertThat(PublicPaths.isPublic(HttpMethod.POST, "/api/members")).isTrue();
        assertThat(PublicPaths.isPublic(HttpMethod.GET, "/api/members/ping")).isTrue();
        assertThat(PublicPaths.isPublic(HttpMethod.GET, "/api/courses/ping")).isTrue();
        assertThat(PublicPaths.isPublic(HttpMethod.GET, "/actuator/health")).isTrue();
    }

    @Test
    @DisplayName("나머지 /api 경로는 전부 보호된다")
    void protectedPaths() {
        assertThat(PublicPaths.isPublic(HttpMethod.GET, "/api/members/1")).isFalse();
        assertThat(PublicPaths.isPublic(HttpMethod.GET, "/api/subscriptions/1")).isFalse();
        assertThat(PublicPaths.isPublic(HttpMethod.GET, "/api/payments/subscriptions/1")).isFalse();
        assertThat(PublicPaths.isPublic(HttpMethod.GET, "/api/courses/1")).isFalse();
        // 가입은 POST만 공개다. 목록 조회는 보호.
        assertThat(PublicPaths.isPublic(HttpMethod.GET, "/api/members")).isFalse();
    }
}
