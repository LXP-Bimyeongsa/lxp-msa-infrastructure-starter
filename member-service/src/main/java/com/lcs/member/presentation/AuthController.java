package com.lcs.member.presentation;

import java.time.Instant;
import java.util.Map;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

// 토큰 발급은 Keycloak이 담당한다 (D-20).
// 이 서비스는 더 이상 로그인 엔드포인트를 제공하지 않는다 —
// 클라이언트는 Keycloak의 토큰 엔드포인트를 직접 사용한다.
@RestController
@RequestMapping("/api/auth")
public class AuthController {

    private final String issuerUri;

    public AuthController(@Value("${keycloak.issuer-uri}") String issuerUri) {
        this.issuerUri = issuerUri;
    }

    @GetMapping("/ping")
    public Map<String, Object> ping() {
        return Map.of(
                "service", "member-service",
                "domain", "auth",
                "status", "UP",
                "timestamp", Instant.now().toString()
        );
    }

    /** 클라이언트가 어디로 로그인해야 하는지 알려준다. */
    @GetMapping("/config")
    public Map<String, Object> config() {
        return Map.of(
                "issuer", issuerUri,
                "tokenEndpoint", issuerUri + "/protocol/openid-connect/token",
                "authorizationEndpoint", issuerUri + "/protocol/openid-connect/auth",
                "clientId", "lxp-web"
        );
    }
}
