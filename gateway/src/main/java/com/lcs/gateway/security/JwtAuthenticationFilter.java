package com.lcs.gateway.security;

import io.jsonwebtoken.Claims;
import io.jsonwebtoken.JwtException;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import java.nio.charset.StandardCharsets;
import javax.crypto.SecretKey;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.cloud.gateway.filter.GatewayFilterChain;
import org.springframework.cloud.gateway.filter.GlobalFilter;
import org.springframework.core.Ordered;
import org.springframework.core.io.buffer.DataBuffer;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.server.reactive.ServerHttpRequest;
import org.springframework.stereotype.Component;
import org.springframework.web.server.ServerWebExchange;
import reactor.core.publisher.Mono;

// JWT 검증은 gateway가 담당한다(D-04). 발급은 member-service.
// 검증 통과 시 memberId를 X-Member-Id 헤더로 다운스트림에 전달한다 —
// 각 서비스는 토큰을 다시 파싱하지 않고 이 헤더를 신뢰한다(신뢰 경계는 gateway).
@Component
public class JwtAuthenticationFilter implements GlobalFilter, Ordered {

    private final SecretKey key;

    public JwtAuthenticationFilter(@Value("${jwt.secret}") String secret) {
        this.key = Keys.hmacShaKeyFor(secret.getBytes(StandardCharsets.UTF_8));
    }

    @Override
    public Mono<Void> filter(ServerWebExchange exchange, GatewayFilterChain chain) {
        ServerHttpRequest request = exchange.getRequest();
        String path = request.getURI().getPath();

        if (PublicPaths.isPublic(request.getMethod(), path)) {
            // 클라이언트가 X-Member-Id를 직접 꽂아 보내는 위장을 차단한다.
            ServerHttpRequest sanitized = request.mutate()
                    .headers(h -> h.remove("X-Member-Id"))
                    .build();
            return chain.filter(exchange.mutate().request(sanitized).build());
        }

        String authorization = request.getHeaders().getFirst(HttpHeaders.AUTHORIZATION);
        if (authorization == null || !authorization.startsWith("Bearer ")) {
            return unauthorized(exchange, "인증 토큰이 없습니다.");
        }

        try {
            Claims claims = Jwts.parser()
                    .verifyWith(key)
                    .build()
                    .parseSignedClaims(authorization.substring(7))
                    .getPayload();

            ServerHttpRequest authenticated = request.mutate()
                    .headers(h -> {
                        h.remove("X-Member-Id");
                        h.set("X-Member-Id", claims.getSubject());
                    })
                    .build();
            return chain.filter(exchange.mutate().request(authenticated).build());
        } catch (JwtException | IllegalArgumentException e) {
            // 서명 불일치 · 만료 · 형식 오류 모두 동일 응답. 원인을 구분해주면 공격자에게 힌트가 된다.
            return unauthorized(exchange, "유효하지 않은 토큰입니다.");
        }
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
