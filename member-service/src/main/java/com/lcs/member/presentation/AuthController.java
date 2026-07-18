package com.lcs.member.presentation;

import java.time.Instant;
import java.util.Map;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

// 인증(JWT 발급)은 member-service가 담당하고 Gateway는 검증만 한다. (docs/DECISIONS.md D-04)
@RestController
@RequestMapping("/api/auth")
public class AuthController {

    @GetMapping("/ping")
    public Map<String, Object> ping() {
        return Map.of(
                "service", "member-service",
                "domain", "auth",
                "status", "UP",
                "timestamp", Instant.now().toString()
        );
    }
}
