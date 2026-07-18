package com.lcs.member.presentation;

import com.lcs.member.application.AuthService;
import com.lcs.member.infrastructure.jwt.JwtTokenProvider;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import java.time.Instant;
import java.util.Map;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

// 인증(JWT 발급)은 member-service가 담당하고 Gateway는 검증만 한다. (docs/DECISIONS.md D-04)
@RestController
@RequestMapping("/api/auth")
public class AuthController {

    private final AuthService authService;

    public AuthController(AuthService authService) {
        this.authService = authService;
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

    @PostMapping("/login")
    public TokenResponse login(@Valid @RequestBody LoginRequest request) {
        JwtTokenProvider.IssuedToken token = authService.login(request.email(), request.password());
        return new TokenResponse(token.accessToken(), "Bearer", token.expiresInSeconds());
    }

    public record LoginRequest(
            @NotBlank @Email String email,
            @NotBlank String password
    ) {
    }

    public record TokenResponse(
            String accessToken,
            String tokenType,
            long expiresIn
    ) {
    }
}
