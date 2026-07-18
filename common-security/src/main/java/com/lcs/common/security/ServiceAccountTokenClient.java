package com.lcs.common.security;

import java.time.Duration;
import java.time.Instant;
import java.util.Map;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;
import org.springframework.web.client.RestTemplate;

/**
 * 서비스가 다른 서비스를 부를 때 쓰는 client credentials 토큰을 발급·캐시한다 (D-34).
 *
 * <p>gateway의 {@code ServiceTokenProvider}와 같은 일을 하지만 그쪽은 WebFlux(Mono)라
 * 코드를 공유할 수 없다. 스택이 다르면 같은 개념이라도 별개 구현이 된다.
 *
 * <p>매 호출 발급하면 Keycloak이 병목이 되므로 만료 전까지 재사용한다.
 * 갱신 여유(skew)를 두는 이유 — 만료 직전 토큰을 보내면 상대가 받았을 때
 * 이미 만료돼 있을 수 있다.
 */
public class ServiceAccountTokenClient {

    private static final Duration REFRESH_SKEW = Duration.ofSeconds(30);

    private final RestTemplate restTemplate;
    private final String tokenUri;
    private final String clientId;
    private final String clientSecret;

    private volatile CachedToken cached;

    public ServiceAccountTokenClient(RestTemplate restTemplate,
                                     String tokenUri,
                                     String clientId,
                                     String clientSecret) {
        this.restTemplate = restTemplate;
        this.tokenUri = tokenUri;
        this.clientId = clientId;
        this.clientSecret = clientSecret;
    }

    /**
     * @throws ServiceTokenUnavailableException 발급 실패. 호출 측은 fail-closed로 다뤄야 한다 —
     *         토큰 없이 호출을 시도해봐야 상대가 거절할 뿐이다.
     */
    public String token() {
        CachedToken current = cached;
        if (current != null && current.usableAt(Instant.now())) {
            return current.value();
        }
        return fetch();
    }

    private String fetch() {
        MultiValueMap<String, String> form = new LinkedMultiValueMap<>();
        form.add("grant_type", "client_credentials");
        form.add("client_id", clientId);
        form.add("client_secret", clientSecret);

        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_FORM_URLENCODED);

        Map<?, ?> response;
        try {
            response = restTemplate.postForObject(tokenUri, new HttpEntity<>(form, headers), Map.class);
        } catch (Exception e) {
            throw new ServiceTokenUnavailableException("서비스 토큰 발급 실패: clientId=" + clientId, e);
        }

        if (response == null || response.get("access_token") == null) {
            throw new ServiceTokenUnavailableException(
                    "서비스 토큰 응답에 access_token이 없습니다: clientId=" + clientId, null);
        }

        String accessToken = (String) response.get("access_token");
        // expires_in이 없으면 캐시하지 않고 매번 받는다 — 만료를 모르는 토큰을 재사용하면
        // 상대가 401을 뱉기 시작할 때까지 알 수 없다.
        Object expiresIn = response.get("expires_in");
        if (expiresIn instanceof Number seconds) {
            this.cached = new CachedToken(accessToken,
                    Instant.now().plusSeconds(seconds.longValue()).minus(REFRESH_SKEW));
        }
        return accessToken;
    }

    private record CachedToken(String value, Instant refreshAt) {

        boolean usableAt(Instant now) {
            return now.isBefore(refreshAt);
        }
    }
}
