package com.lcs.gateway.security;

// Keycloak에 토큰 상태를 물어보지 못했다 (D-35).
//
// "토큰이 죽었다"와 "살았는지 모르겠다"는 다르다. 전자는 401, 후자는 503이다.
// 섞으면 Keycloak 장애가 "당신 토큰이 잘못됐다"로 표시돼 사용자가 재로그인을 시도하고,
// 그 재로그인도 Keycloak이 죽어서 실패한다.
public class IntrospectionUnavailableException extends RuntimeException {

    public IntrospectionUnavailableException(Throwable cause) {
        super("Keycloak introspection 호출 실패", cause);
    }
}
