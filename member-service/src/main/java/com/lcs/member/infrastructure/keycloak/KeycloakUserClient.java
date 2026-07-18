package com.lcs.member.infrastructure.keycloak;

import java.util.List;
import java.util.Map;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.web.client.RestTemplateBuilder;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;
import org.springframework.web.client.RestTemplate;

// Keycloak Admin API 호출. 자격증명은 Keycloak이 소유하므로
// 가입 시 이쪽에 사용자를 만들고, 도메인 프로필은 member_db에 둔다 (D-20).
@Component
public class KeycloakUserClient {

    private static final Logger log = LoggerFactory.getLogger(KeycloakUserClient.class);

    private final RestTemplate restTemplate;
    private final String serverUrl;
    private final String realm;
    private final String clientId;
    private final String clientSecret;

    public KeycloakUserClient(RestTemplateBuilder builder,
                              @Value("${keycloak.admin.server-url}") String serverUrl,
                              @Value("${keycloak.admin.realm}") String realm,
                              @Value("${keycloak.admin.client-id}") String clientId,
                              @Value("${keycloak.admin.client-secret}") String clientSecret) {
        this.restTemplate = builder.build();
        this.serverUrl = serverUrl;
        this.realm = realm;
        this.clientId = clientId;
        this.clientSecret = clientSecret;
    }

    /**
     * Keycloak에 사용자를 만들고 내부 memberId를 속성으로 심는다.
     * gateway가 이 속성을 클레임으로 받아 X-Member-Id로 전달한다.
     *
     * @return 생성된 사용자의 Keycloak sub
     */
    public String createUser(String email, String rawPassword, Long memberId) {
        String token = fetchServiceAccountToken();

        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        headers.setBearerAuth(token);

        Map<String, Object> body = Map.of(
                "username", email,
                "email", email,
                "enabled", true,
                "emailVerified", true,
                // 문자열 리스트여야 한다. 숫자로 넣으면 Keycloak이 거부한다.
                "attributes", Map.of("member_id", List.of(String.valueOf(memberId))),
                "credentials", List.of(Map.of(
                        "type", "password",
                        "value", rawPassword,
                        "temporary", false))
        );

        try {
            restTemplate.postForEntity(
                    serverUrl + "/admin/realms/" + realm + "/users",
                    new HttpEntity<>(body, headers), Void.class);
        } catch (Exception e) {
            throw new KeycloakUserCreationException(
                    "Keycloak 사용자 생성 실패: " + email, e);
        }

        return findUserId(email, token);
    }

    /** 보상 처리용. member_db 저장이 실패하면 Keycloak 쪽도 되돌린다 (P-10). */
    public void deleteUser(String keycloakUserId) {
        try {
            HttpHeaders headers = new HttpHeaders();
            headers.setBearerAuth(fetchServiceAccountToken());
            restTemplate.exchange(
                    serverUrl + "/admin/realms/" + realm + "/users/" + keycloakUserId,
                    org.springframework.http.HttpMethod.DELETE,
                    new HttpEntity<>(headers), Void.class);
        } catch (Exception e) {
            // 보상 실패는 삼키고 로그만 남긴다. 원래 예외를 덮으면 안 된다.
            log.error("Keycloak 사용자 보상 삭제 실패 — 수동 정리 필요: userId={}", keycloakUserId, e);
        }
    }

    private String fetchServiceAccountToken() {
        MultiValueMap<String, String> form = new LinkedMultiValueMap<>();
        form.add("grant_type", "client_credentials");
        form.add("client_id", clientId);
        form.add("client_secret", clientSecret);

        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_FORM_URLENCODED);

        Map<?, ?> response = restTemplate.postForObject(
                serverUrl + "/realms/" + realm + "/protocol/openid-connect/token",
                new HttpEntity<>(form, headers), Map.class);

        if (response == null || response.get("access_token") == null) {
            throw new KeycloakUserCreationException("Keycloak 서비스 계정 토큰 발급 실패", null);
        }
        return (String) response.get("access_token");
    }

    private String findUserId(String email, String token) {
        HttpHeaders headers = new HttpHeaders();
        headers.setBearerAuth(token);

        List<?> found = restTemplate.exchange(
                serverUrl + "/admin/realms/" + realm + "/users?exact=true&username=" + email,
                org.springframework.http.HttpMethod.GET,
                new HttpEntity<>(headers), List.class).getBody();

        if (found == null || found.isEmpty()) {
            throw new KeycloakUserCreationException("생성한 사용자를 찾을 수 없음: " + email, null);
        }
        return (String) ((Map<?, ?>) found.get(0)).get("id");
    }
}
