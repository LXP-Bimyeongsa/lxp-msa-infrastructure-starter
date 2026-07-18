package com.lcs.member.infrastructure.keycloak;

public class KeycloakUserCreationException extends RuntimeException {

    public KeycloakUserCreationException(String message, Throwable cause) {
        super(message, cause);
    }
}
