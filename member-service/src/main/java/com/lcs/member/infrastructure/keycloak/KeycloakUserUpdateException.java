package com.lcs.member.infrastructure.keycloak;

// 기존 Keycloak 사용자를 고치다 실패한 경우 (탈퇴 시 비활성화 등, D-32).
// 생성 실패(KeycloakUserCreationException)와 구분한다 — 가입 경로의 보상 처리와
// 탈퇴 경로의 롤백은 다뤄야 할 상황이 다르다.
public class KeycloakUserUpdateException extends RuntimeException {

    public KeycloakUserUpdateException(String message, Throwable cause) {
        super(message, cause);
    }
}
