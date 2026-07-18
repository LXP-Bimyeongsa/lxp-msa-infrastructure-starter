package com.lcs.common.security;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.Instant;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.security.oauth2.jwt.Jwt;

// gateway 우회 차단의 핵심 판단 지점 (D-33).
// 여기가 느슨하면 P-11이 그대로 남는다.
class InternalAudienceValidatorTest {

    private final InternalAudienceValidator validator = new InternalAudienceValidator("lxp-internal");

    @Test
    @DisplayName("gateway 서비스 토큰(aud에 lxp-internal 포함)은 통과한다")
    void acceptsServiceToken() {
        assertThat(validator.validate(jwtWithAudience(List.of("lxp-internal"))).hasErrors()).isFalse();
    }

    @Test
    @DisplayName("사용자 토큰은 거부한다 — 서명은 유효해도 audience가 다르다")
    void rejectsUserToken() {
        // lxp-web이 발급한 사용자 토큰. 같은 realm이 서명하므로 서명 검증만으로는 통과한다.
        assertThat(validator.validate(jwtWithAudience(List.of("account"))).hasErrors()).isTrue();
    }

    @Test
    @DisplayName("audience가 없는 토큰은 거부한다")
    void rejectsMissingAudience() {
        assertThat(validator.validate(jwtWithAudience(List.of())).hasErrors()).isTrue();
    }

    @Test
    @DisplayName("여러 audience 중 하나만 맞아도 통과한다")
    void acceptsAmongMultipleAudiences() {
        assertThat(validator.validate(jwtWithAudience(List.of("account", "lxp-internal")))
                .hasErrors()).isFalse();
    }

    private Jwt jwtWithAudience(List<String> audience) {
        return Jwt.withTokenValue("token")
                .header("alg", "RS256")
                .claim("sub", "service-account-lxp-gateway")
                .audience(audience)
                .issuedAt(Instant.now())
                .expiresAt(Instant.now().plusSeconds(300))
                .build();
    }
}
