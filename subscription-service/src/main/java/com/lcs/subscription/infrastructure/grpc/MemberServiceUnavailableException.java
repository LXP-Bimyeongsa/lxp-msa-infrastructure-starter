package com.lcs.subscription.infrastructure.grpc;

// member-service와 통신할 수 없음. 서킷브레이커가 실패로 집계하는 예외.
public class MemberServiceUnavailableException extends RuntimeException {

    public MemberServiceUnavailableException(String message, Throwable cause) {
        super(message, cause);
    }
}
