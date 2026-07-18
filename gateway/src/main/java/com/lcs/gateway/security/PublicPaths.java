package com.lcs.gateway.security;

import org.springframework.http.HttpMethod;

// 인증 없이 통과시키는 경로의 단일 정의.
// 필터에서 분리한 이유: 순수 함수라 WebFlux 없이 단위 테스트가 된다.
public final class PublicPaths {

    private PublicPaths() {
    }

    public static boolean isPublic(HttpMethod method, String path) {
        // 로그인 등 인증 자체를 위한 경로
        if (path.startsWith("/api/auth/")) {
            return true;
        }
        // 회원 가입 — 토큰이 없어야 정상인 유일한 쓰기 경로
        if (HttpMethod.POST.equals(method) && path.equals("/api/members")) {
            return true;
        }
        // 스모크 테스트용 ping
        if (path.endsWith("/ping")) {
            return true;
        }
        // gateway 라우트는 /api/** 뿐이다. 그 외(actuator 등)는 라우팅 대상이 아니므로 통과.
        return !path.startsWith("/api/");
    }
}
