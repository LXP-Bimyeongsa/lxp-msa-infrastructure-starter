package com.lcs.gateway.security;

import java.time.Duration;
import java.time.Instant;
import java.util.Map;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Component;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;
import org.springframework.web.reactive.function.BodyInserters;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;

/**
 * gateway를 거쳤다는 증명으로 쓰는 서비스 토큰을 발급·캐시한다 (D-33).
 *
 * <p>Keycloak client credentials로 받은 토큰에는 {@code aud: lxp-internal}이 실려 있고,
 * 이 audience를 넣을 수 있는 클라이언트는 {@code lxp-gateway} 하나뿐이다. 시크릿이 없으면
 * 만들 수 없으므로, 다운스트림은 이 토큰이 붙어 있다는 것만으로 gateway 경유를 확신한다.
 *
 * <p>매 요청 발급하면 Keycloak이 병목이 되므로 만료 전까지 재사용한다.
 * 갱신 여유(skew)를 두는 이유 — 만료 직전 토큰을 넘기면 다운스트림에 도착했을 때
 * 이미 만료돼 있을 수 있다.
 */
@Component
public class ServiceTokenProvider {

    private static final Logger log = LoggerFactory.getLogger(ServiceTokenProvider.class);

    // 만료 이 시간 전부터는 새로 받는다.
    private static final Duration REFRESH_SKEW = Duration.ofSeconds(30);

    private final WebClient webClient;
    private final String tokenUri;
    private final String clientId;
    private final String clientSecret;

    private volatile CachedToken cached;

    public ServiceTokenProvider(WebClient.Builder builder,
                                @Value("${keycloak.service-token.token-uri}") String tokenUri,
                                @Value("${keycloak.service-token.client-id}") String clientId,
                                @Value("${keycloak.service-token.client-secret}") String clientSecret) {
        this.webClient = builder.build();
        this.tokenUri = tokenUri;
        this.clientId = clientId;
        this.clientSecret = clientSecret;
    }

    public Mono<String> token() {
        CachedToken current = cached;
        if (current != null && current.usableAt(Instant.now())) {
            return Mono.just(current.value());
        }
        return fetch();
    }

    private Mono<String> fetch() {
        MultiValueMap<String, String> form = new LinkedMultiValueMap<>();
        form.add("grant_type", "client_credentials");
        form.add("client_id", clientId);
        form.add("client_secret", clientSecret);

        return webClient.post()
                .uri(tokenUri)
                .contentType(MediaType.APPLICATION_FORM_URLENCODED)
                .body(BodyInserters.fromFormData(form))
                .retrieve()
                .bodyToMono(Map.class)
                .map(this::cache)
                .doOnError(e -> log.error("서비스 토큰 발급 실패: {}", e.getMessage()));
    }

    @SuppressWarnings("unchecked")
    private String cache(Map<String, Object> response) {
        String accessToken = (String) response.get("access_token");
        if (accessToken == null) {
            throw new IllegalStateException("서비스 토큰 응답에 access_token이 없습니다.");
        }
        // expires_in이 없으면 캐시하지 않고 매번 받는다 — 만료를 모르는 토큰을 재사용하면
        // 다운스트림이 401을 뱉기 시작할 때까지 알 수 없다.
        Number expiresIn = (Number) response.get("expires_in");
        if (expiresIn != null) {
            this.cached = new CachedToken(accessToken,
                    Instant.now().plusSeconds(expiresIn.longValue()).minus(REFRESH_SKEW));
        }
        return accessToken;
    }

    private record CachedToken(String value, Instant refreshAt) {

        boolean usableAt(Instant now) {
            return now.isBefore(refreshAt);
        }
    }
}
