package com.lcs.gateway.security;

import java.time.Duration;
import java.time.Instant;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
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
 * 토큰이 <b>아직</b> 유효한지 Keycloak에 물어본다 (D-35, P-17).
 *
 * <p>서명 검증만으로는 탈퇴·차단된 회원을 걸러낼 수 없다. JWT는 발급 시점의 사실을
 * 담은 종이일 뿐이라, 그 뒤에 계정이 비활성화돼도(D-32) 만료 전까지는 그대로 유효하다.
 * introspection(RFC 7662)은 Keycloak에 "이 토큰 지금도 살아 있냐"를 묻는다 —
 * 탈퇴 시 세션을 끊었으므로(D-32) Keycloak은 inactive로 답한다.
 *
 * <p><b>캐시를 두는 이유</b> — 매 요청 Keycloak을 부르면 gateway 처리량이 Keycloak에
 * 묶인다. 활성 판정만 짧게 캐시한다. 노출 창은 토큰 수명(300초)에서 캐시 TTL로 줄어든다.
 * 비활성 판정은 캐시하지 않는다 — 어차피 그 요청은 거절되고, 재활성화가 즉시 반영돼야 한다.
 *
 * <p><b>왜 gateway에서만 하는가</b> — 다운스트림은 이미 gateway가 붙인 서비스 토큰만
 * 받는다(D-33·D-34). 사용자 토큰이 닿는 곳은 gateway 하나뿐이므로 확인 지점도 하나면 된다.
 */
@Component
public class TokenIntrospector {

    private static final Logger log = LoggerFactory.getLogger(TokenIntrospector.class);

    // 캐시가 무한히 자라지 않도록 상한을 둔다. 넘으면 만료된 항목을 걷어낸다.
    private static final int MAX_CACHE_ENTRIES = 10_000;

    private final WebClient webClient;
    private final boolean enabled;
    private final String introspectionUri;
    private final String clientId;
    private final String clientSecret;
    private final Duration cacheTtl;

    private final ConcurrentHashMap<String, Instant> activeUntil = new ConcurrentHashMap<>();

    public TokenIntrospector(WebClient.Builder builder,
                             @Value("${keycloak.introspection.enabled:true}") boolean enabled,
                             @Value("${keycloak.introspection.uri:}") String introspectionUri,
                             @Value("${keycloak.service-token.client-id}") String clientId,
                             @Value("${keycloak.service-token.client-secret}") String clientSecret,
                             @Value("${keycloak.introspection.cache-ttl-seconds:30}") long cacheTtlSeconds) {
        this.webClient = builder.build();
        this.enabled = enabled;
        this.introspectionUri = introspectionUri;
        this.clientId = clientId;
        this.clientSecret = clientSecret;
        this.cacheTtl = Duration.ofSeconds(cacheTtlSeconds);
        if (enabled) {
            log.info("토큰 introspection 활성 — 캐시 TTL={}초", cacheTtlSeconds);
        } else {
            log.warn("토큰 introspection 비활성 — 탈퇴 회원의 토큰이 만료까지 통과한다 (P-17)");
        }
    }

    /**
     * @return 토큰이 지금도 유효하면 true.
     *         Keycloak 조회에 실패하면 {@link IntrospectionUnavailableException}으로 끝난다 —
     *         호출 측이 fail-closed로 다룰 수 있게 "모른다"와 "죽었다"를 구분한다.
     */
    public Mono<Boolean> isActive(String token) {
        if (!enabled) {
            return Mono.just(true);
        }
        Instant cached = activeUntil.get(token);
        if (cached != null && Instant.now().isBefore(cached)) {
            return Mono.just(true);
        }
        return introspect(token);
    }

    private Mono<Boolean> introspect(String token) {
        MultiValueMap<String, String> form = new LinkedMultiValueMap<>();
        form.add("token", token);
        form.add("client_id", clientId);
        form.add("client_secret", clientSecret);

        return webClient.post()
                .uri(introspectionUri)
                .contentType(MediaType.APPLICATION_FORM_URLENCODED)
                .body(BodyInserters.fromFormData(form))
                .retrieve()
                .bodyToMono(Map.class)
                .map(response -> {
                    boolean active = Boolean.TRUE.equals(response.get("active"));
                    if (active) {
                        remember(token);
                    }
                    return active;
                })
                .onErrorMap(e -> !(e instanceof IntrospectionUnavailableException),
                        e -> new IntrospectionUnavailableException(e));
    }

    private void remember(String token) {
        if (activeUntil.size() >= MAX_CACHE_ENTRIES) {
            Instant now = Instant.now();
            activeUntil.entrySet().removeIf(entry -> now.isAfter(entry.getValue()));
        }
        activeUntil.put(token, Instant.now().plus(cacheTtl));
    }
}
