package com.lcs.member.infrastructure.jwt;

import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.time.Instant;
import java.util.Date;
import javax.crypto.SecretKey;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

// 발급만 담당한다. 검증은 gateway가 같은 시크릿으로 수행한다(D-04).
// 시크릿은 config-repo/application.yml에서 양쪽에 공통 주입된다.
@Component
public class JwtTokenProvider {

    private final SecretKey key;
    private final Duration ttl;

    public JwtTokenProvider(
            @Value("${jwt.secret}") String secret,
            @Value("${jwt.access-token-ttl-seconds:3600}") long ttlSeconds) {
        // HS256은 32바이트 이상 시크릿을 요구한다. 짧으면 여기서 즉시 실패한다.
        this.key = Keys.hmacShaKeyFor(secret.getBytes(StandardCharsets.UTF_8));
        this.ttl = Duration.ofSeconds(ttlSeconds);
    }

    public IssuedToken issue(Long memberId, String email) {
        Instant now = Instant.now();
        Instant expiresAt = now.plus(ttl);
        String token = Jwts.builder()
                .subject(String.valueOf(memberId))
                .claim("email", email)
                .issuedAt(Date.from(now))
                .expiration(Date.from(expiresAt))
                .signWith(key)
                .compact();
        return new IssuedToken(token, ttl.toSeconds());
    }

    public record IssuedToken(String accessToken, long expiresInSeconds) {
    }
}
