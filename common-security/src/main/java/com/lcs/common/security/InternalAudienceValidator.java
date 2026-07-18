package com.lcs.common.security;

import org.springframework.security.oauth2.core.OAuth2Error;
import org.springframework.security.oauth2.core.OAuth2TokenValidator;
import org.springframework.security.oauth2.core.OAuth2TokenValidatorResult;
import org.springframework.security.oauth2.jwt.Jwt;

/**
 * 토큰이 gateway가 받은 서비스 토큰인지 확인한다 (D-33).
 *
 * <p>이 audience를 실을 수 있는 Keycloak 클라이언트는 {@code lxp-gateway} 하나뿐이고,
 * 그 토큰은 client secret 없이는 발급받을 수 없다. 따라서 audience 확인이
 * 곧 "gateway를 거쳤다"의 증명이다.
 *
 * <p>서명 검증만으로는 부족한 이유 — 사용자 토큰도 같은 realm이 서명하므로
 * 서명은 통과한다. 사용자가 자기 토큰을 들고 서비스를 직접 호출하면서
 * {@code X-Member-Id}에 남의 id를 넣는 것을 막아야 한다.
 */
public class InternalAudienceValidator implements OAuth2TokenValidator<Jwt> {

    private final String requiredAudience;

    public InternalAudienceValidator(String requiredAudience) {
        this.requiredAudience = requiredAudience;
    }

    @Override
    public OAuth2TokenValidatorResult validate(Jwt token) {
        if (token.getAudience() != null && token.getAudience().contains(requiredAudience)) {
            return OAuth2TokenValidatorResult.success();
        }
        return OAuth2TokenValidatorResult.failure(new OAuth2Error(
                "invalid_token",
                "이 서비스는 gateway를 거친 요청만 받는다 (audience=" + requiredAudience + ")",
                null));
    }
}
