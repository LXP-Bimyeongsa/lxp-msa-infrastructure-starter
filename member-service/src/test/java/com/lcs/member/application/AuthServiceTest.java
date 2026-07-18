package com.lcs.member.application;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.lcs.member.infrastructure.jwt.JwtTokenProvider;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;

@SpringBootTest
@ActiveProfiles("test")
class AuthServiceTest {

    @Autowired
    private MemberService memberService;

    @Autowired
    private AuthService authService;

    @Test
    @DisplayName("올바른 자격증명이면 토큰이 발급된다")
    void loginIssuesToken() {
        memberService.register("login@lxp.dev", "password1234", "로그인");

        JwtTokenProvider.IssuedToken token = authService.login("login@lxp.dev", "password1234");

        // JWT는 header.payload.signature 세 조각이다
        assertThat(token.accessToken().split("\\.")).hasSize(3);
        assertThat(token.expiresInSeconds()).isPositive();
    }

    @Test
    @DisplayName("비밀번호가 틀리면 거부된다")
    void rejectsWrongPassword() {
        memberService.register("wrong@lxp.dev", "password1234", "틀림");

        assertThatThrownBy(() -> authService.login("wrong@lxp.dev", "nope-nope-nope"))
                .isInstanceOf(InvalidCredentialsException.class);
    }

    @Test
    @DisplayName("없는 이메일도 같은 예외로 거부된다 — 가입 여부를 밖에서 알 수 없어야 한다")
    void rejectsUnknownEmailWithSameError() {
        assertThatThrownBy(() -> authService.login("ghost@lxp.dev", "password1234"))
                .isInstanceOf(InvalidCredentialsException.class);
    }
}
