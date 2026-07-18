package com.lcs.gateway.security;

import java.nio.charset.StandardCharsets;
import org.springframework.cloud.gateway.filter.GatewayFilterChain;
import org.springframework.cloud.gateway.filter.GlobalFilter;
import org.springframework.core.Ordered;
import org.springframework.core.io.buffer.DataBuffer;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.server.reactive.ServerHttpRequest;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.jwt.ReactiveJwtDecoder;
import org.springframework.stereotype.Component;
import org.springframework.web.server.ServerWebExchange;
import reactor.core.publisher.Mono;

// 토큰 검증은 gateway가 전담한다. 발급은 Keycloak (D-20).
//
// 검증 통과 시 Keycloak의 sub를 X-Member-Id 헤더로 다운스트림에 전달한다.
// 각 서비스는 토큰을 다시 파싱하지 않고 이 헤더를 신뢰한다 —
// 신뢰 경계가 gateway이기 때문이다. 그래서 클라이언트가 직접 보낸
// X-Member-Id는 어떤 경로에서든 반드시 제거해야 한다.
@Component
public class JwtAuthenticationFilter implements GlobalFilter, Ordered {

    static final String MEMBER_ID_HEADER = "X-Member-Id";

    // Keycloak sub는 UUID지만, 도메인 서비스들은 숫자 memberId를 쓴다.
    // sub를 그대로 내려보내면 subscription/payment/course의 컬럼 타입과
    // gRPC 계약까지 전부 바꿔야 한다. 대신 가입 시 Keycloak 사용자 속성에
    // 내부 memberId를 심고, 그것을 클레임으로 받아 전달한다.
    private static final String MEMBER_ID_CLAIM = "member_id";

    private final ReactiveJwtDecoder jwtDecoder;

    public JwtAuthenticationFilter(ReactiveJwtDecoder jwtDecoder) {
        this.jwtDecoder = jwtDecoder;
    }

    @Override
    public Mono<Void> filter(ServerWebExchange exchange, GatewayFilterChain chain) {
        ServerHttpRequest request = exchange.getRequest();

        if (PublicPaths.isPublic(request.getMethod(), request.getURI().getPath())) {
            return chain.filter(exchange.mutate().request(stripMemberId(request)).build());
        }

        String authorization = request.getHeaders().getFirst(HttpHeaders.AUTHORIZATION);
        if (authorization == null || !authorization.startsWith("Bearer ")) {
            return unauthorized(exchange, "인증 토큰이 없습니다.");
        }

        return jwtDecoder.decode(authorization.substring(7))
                .flatMap(jwt -> {
                    String memberId = jwt.getClaimAsString(MEMBER_ID_CLAIM);
                    if (memberId == null) {
                        // Keycloak에는 있으나 member_id 속성이 없는 계정.
                        // 가입 절차를 거치지 않았다는 뜻이므로 통과시키지 않는다.
                        return unauthorized(exchange, "가입이 완료되지 않은 계정입니다.");
                    }
                    return chain.filter(exchange.mutate()
                            .request(withMemberId(request, memberId))
                            .build());
                })
                // 서명 불일치·만료·형식 오류를 구분하지 않는다. 알려주면 공격자에게 힌트가 된다.
                .onErrorResume(e -> unauthorized(exchange, "유효하지 않은 토큰입니다."));
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

    private Mono<Void> unauthorized(ServerWebExchange exchange, String message) {
        exchange.getResponse().setStatusCode(HttpStatus.UNAUTHORIZED);
        exchange.getResponse().getHeaders().setContentType(MediaType.APPLICATION_JSON);
        String body = "{\"status\":401,\"error\":\"Unauthorized\",\"message\":\"" + message + "\"}";
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
