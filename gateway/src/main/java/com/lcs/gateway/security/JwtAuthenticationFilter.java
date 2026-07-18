package com.lcs.gateway.security;

import java.nio.charset.StandardCharsets;
import java.util.Optional;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.cloud.gateway.filter.GatewayFilterChain;
import org.springframework.cloud.gateway.filter.GlobalFilter;
import org.springframework.core.Ordered;
import org.springframework.core.io.buffer.DataBuffer;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.server.reactive.ServerHttpRequest;
import org.springframework.security.oauth2.jwt.ReactiveJwtDecoder;
import org.springframework.stereotype.Component;
import org.springframework.web.server.ServerWebExchange;
import reactor.core.publisher.Mono;

// 토큰 검증은 gateway가 전담한다. 발급은 Keycloak (D-20).
//
// 검증 통과 시 내부 memberId를 X-Member-Id 헤더로 다운스트림에 전달한다.
// 각 서비스는 토큰을 다시 파싱하지 않고 이 헤더를 신뢰한다 —
// 신뢰 경계가 gateway이기 때문이다. 그래서 클라이언트가 직접 보낸
// X-Member-Id는 어떤 경로에서든 반드시 제거해야 한다.
//
// 다만 "gateway를 거쳤다"는 것 자체를 다운스트림이 확인할 수 있어야 한다(D-33).
// 그래서 사용자 토큰을 서비스 토큰으로 갈아끼워 보낸다. 사용자 토큰을 그대로
// 넘기지 않는 이유 — 다운스트림이 필요로 하는 것은 "이 요청이 gateway를 거쳤는가"이지
// 사용자 자격증명이 아니다. 토큰이 더 멀리 퍼질수록 새어나갈 지점이 늘어난다.
@Component
public class JwtAuthenticationFilter implements GlobalFilter, Ordered {

    static final String MEMBER_ID_HEADER = "X-Member-Id";

    private static final Logger log = LoggerFactory.getLogger(JwtAuthenticationFilter.class);

    // Keycloak sub는 UUID지만, 도메인 서비스들은 숫자 memberId를 쓴다.
    // sub를 그대로 내려보내면 subscription/payment/course의 컬럼 타입과
    // gRPC 계약까지 전부 바꿔야 한다. 대신 가입 시 Keycloak 사용자 속성에
    // 내부 memberId를 심고, 그것을 클레임으로 받아 전달한다.
    private static final String MEMBER_ID_CLAIM = "member_id";

    private final ReactiveJwtDecoder jwtDecoder;
    private final ServiceTokenProvider serviceTokenProvider;

    public JwtAuthenticationFilter(ReactiveJwtDecoder jwtDecoder,
                                   ServiceTokenProvider serviceTokenProvider) {
        this.jwtDecoder = jwtDecoder;
        this.serviceTokenProvider = serviceTokenProvider;
    }

    @Override
    public Mono<Void> filter(ServerWebExchange exchange, GatewayFilterChain chain) {
        ServerHttpRequest request = exchange.getRequest();

        // 공개 경로도 다운스트림에는 서비스 토큰을 달고 나간다.
        // 여기서 빼면 "가입 엔드포인트만 gateway 없이 직접 호출 가능"한 구멍이 생긴다.
        if (PublicPaths.isPublic(request.getMethod(), request.getURI().getPath())) {
            return forward(exchange, chain, stripMemberId(request));
        }

        String authorization = request.getHeaders().getFirst(HttpHeaders.AUTHORIZATION);
        if (authorization == null || !authorization.startsWith("Bearer ")) {
            return unauthorized(exchange, "인증 토큰이 없습니다.");
        }

        // 검증 결과를 Optional로 감싸 값을 실어 나른다.
        // Mono<Void>는 값 없이 완료되므로 switchIfEmpty로 실패를 구분하려 하면
        // 정상 응답까지 실패로 잡힌다.
        return jwtDecoder.decode(authorization.substring(7))
                .map(jwt -> Optional.ofNullable(jwt.getClaimAsString(MEMBER_ID_CLAIM)))
                // 서명 불일치·만료·형식 오류를 구분하지 않는다. 알려주면 공격자에게 힌트가 된다.
                .onErrorReturn(Optional.empty())
                .flatMap(memberId -> memberId
                        .map(id -> forward(exchange, chain, withMemberId(request, id)))
                        // 토큰은 유효하나 member_id 속성이 없는 계정 = 가입 절차 미완.
                        // 메시지는 나뉘지만 둘 다 401이라 존재 여부는 새지 않는다.
                        .orElseGet(() -> unauthorized(exchange, "유효하지 않거나 가입이 완료되지 않은 계정입니다.")));
    }

    /**
     * 서비스 토큰을 붙여 다운스트림으로 넘긴다 (D-33).
     *
     * <p>발급 실패 시 fail-closed로 503을 낸다. 토큰 없이 통과시키면 다운스트림이
     * 401을 뱉을 뿐이고, 반대로 다운스트림이 토큰을 요구하지 않는 상태였다면
     * 우회 차단이 조용히 꺼진다. D-18과 같은 판단이다.
     */
    private Mono<Void> forward(ServerWebExchange exchange, GatewayFilterChain chain,
                               ServerHttpRequest request) {
        return serviceTokenProvider.token()
                .map(Optional::of)
                .onErrorResume(e -> {
                    log.error("서비스 토큰 발급 실패 — 요청을 거부한다: {}", e.getMessage());
                    return Mono.just(Optional.<String>empty());
                })
                .flatMap(token -> token
                        .map(value -> chain.filter(exchange.mutate()
                                .request(withServiceToken(request, value))
                                .build()))
                        .orElseGet(() -> serviceUnavailable(exchange)));
    }

    private ServerHttpRequest stripMemberId(ServerHttpRequest request) {
        return request.mutate().headers(h -> h.remove(MEMBER_ID_HEADER)).build();
    }

    private ServerHttpRequest withMemberId(ServerHttpRequest request, String memberId) {
        return request.mutate()
                .headers(h -> {
                    h.remove(MEMBER_ID_HEADER);
                    h.set(MEMBER_ID_HEADER, memberId);
                })
                .build();
    }

    // 사용자 토큰을 서비스 토큰으로 갈아끼운다. 사용자 토큰은 여기서 멈춘다.
    private ServerHttpRequest withServiceToken(ServerHttpRequest request, String serviceToken) {
        return request.mutate()
                .headers(h -> h.set(HttpHeaders.AUTHORIZATION, "Bearer " + serviceToken))
                .build();
    }

    private Mono<Void> unauthorized(ServerWebExchange exchange, String message) {
        return write(exchange, HttpStatus.UNAUTHORIZED, "Unauthorized", message);
    }

    private Mono<Void> serviceUnavailable(ServerWebExchange exchange) {
        return write(exchange, HttpStatus.SERVICE_UNAVAILABLE, "Service Unavailable",
                "인증 서버를 사용할 수 없습니다.");
    }

    private Mono<Void> write(ServerWebExchange exchange, HttpStatus status, String error, String message) {
        exchange.getResponse().setStatusCode(status);
        exchange.getResponse().getHeaders().setContentType(MediaType.APPLICATION_JSON);
        String body = "{\"status\":" + status.value() + ",\"error\":\"" + error
                + "\",\"message\":\"" + message + "\"}";
        DataBuffer buffer = exchange.getResponse().bufferFactory()
                .wrap(body.getBytes(StandardCharsets.UTF_8));
        return exchange.getResponse().writeWith(Mono.just(buffer));
    }

    @Override
    public int getOrder() {
        // 라우팅보다 먼저 실행돼야 한다.
        return -100;
    }
}
