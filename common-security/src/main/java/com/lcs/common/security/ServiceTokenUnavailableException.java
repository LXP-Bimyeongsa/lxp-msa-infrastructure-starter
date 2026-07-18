package com.lcs.common.security;

// 서비스 토큰을 받지 못했다 (D-34).
// 호출 측은 fail-closed로 다뤄야 한다 — 토큰 없이 호출해봐야 상대가 거절할 뿐이고,
// "인증을 못 했다"를 "상대가 죽었다"로 잘못 읽으면 엉뚱한 곳을 보게 된다.
public class ServiceTokenUnavailableException extends RuntimeException {

    public ServiceTokenUnavailableException(String message, Throwable cause) {
        super(message, cause);
    }
}
