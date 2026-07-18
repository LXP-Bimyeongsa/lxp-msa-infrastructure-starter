package com.lcs.gateway.security;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.oauth2.core.OAuth2TokenValidator;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.jwt.JwtValidators;
import org.springframework.security.oauth2.jwt.NimbusReactiveJwtDecoder;
import org.springframework.security.oauth2.jwt.ReactiveJwtDecoder;

// Keycloak 토큰 검증기 (D-20).
//
// 여기가 P-09에서 예고한 함정 지점이다.
// 토큰의 iss는 "클라이언트가 접속한 주소"(http://localhost:8180/realms/lxp)로 발급되는데,
// gateway는 도커 네트워크 안에 있어서 localhost:8180으로 나가면 자기 자신을 가리킨다.
//
// 그래서 둘을 분리한다.
//   - JWKS 조회: 내부 주소(http://keycloak:8080/...)로 실제 통신
//   - issuer 검증: 외부 주소로 문자열 비교
// 하나로 묶으면 JWKS를 못 가져오거나 iss 불일치로 전부 401이 된다.
@Configuration
public class JwtDecoderConfiguration {

    @Bean
    public ReactiveJwtDecoder reactiveJwtDecoder(
            @Value("${keycloak.jwk-set-uri}") String jwkSetUri,
            @Value("${keycloak.issuer-uri}") String issuerUri) {

        NimbusReactiveJwtDecoder decoder = NimbusReactiveJwtDecoder
                .withJwkSetUri(jwkSetUri)
                .build();

        // 기본 검증(만료 등) + iss가 우리가 아는 발급자인지 확인.
        // iss 검증을 빼면 다른 Keycloak realm이 발급한 토큰도 통과한다.
        OAuth2TokenValidator<Jwt> validator = JwtValidators.createDefaultWithIssuer(issuerUri);
        decoder.setJwtValidator(validator);
        return decoder;
    }
}
