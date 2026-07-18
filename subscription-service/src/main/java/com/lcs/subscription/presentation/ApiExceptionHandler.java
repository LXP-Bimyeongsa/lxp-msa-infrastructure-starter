package com.lcs.subscription.presentation;

import com.lcs.subscription.application.InactiveMemberException;
import com.lcs.subscription.application.MemberVerificationUnavailableException;
import com.lcs.subscription.application.SubscriptionNotFoundException;
import com.lcs.subscription.infrastructure.grpc.MemberNotFoundOnRemoteException;
import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.Map;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.MissingRequestHeaderException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

@RestControllerAdvice
public class ApiExceptionHandler {

    @ExceptionHandler(SubscriptionNotFoundException.class)
    public ResponseEntity<Map<String, Object>> handleNotFound(SubscriptionNotFoundException e) {
        return build(HttpStatus.NOT_FOUND, e.getMessage());
    }

    @ExceptionHandler(MemberNotFoundOnRemoteException.class)
    public ResponseEntity<Map<String, Object>> handleMemberNotFound(MemberNotFoundOnRemoteException e) {
        return build(HttpStatus.BAD_REQUEST, e.getMessage());
    }

    @ExceptionHandler(InactiveMemberException.class)
    public ResponseEntity<Map<String, Object>> handleInactiveMember(InactiveMemberException e) {
        return build(HttpStatus.BAD_REQUEST, e.getMessage());
    }

    @ExceptionHandler(MemberVerificationUnavailableException.class)
    public ResponseEntity<Map<String, Object>> handleVerificationUnavailable(
            MemberVerificationUnavailableException e) {
        // fail-closed. 회원 확인이 불가능하면 구독을 만들지 않는다(D-18).
        return build(HttpStatus.SERVICE_UNAVAILABLE, e.getMessage());
    }

    @ExceptionHandler(MissingRequestHeaderException.class)
    public ResponseEntity<Map<String, Object>> handleMissingHeader(MissingRequestHeaderException e) {
        // X-Member-Id 누락 — gateway를 거치지 않았거나 토큰이 없는 요청
        return build(HttpStatus.UNAUTHORIZED, "인증 정보가 없습니다.");
    }

    private ResponseEntity<Map<String, Object>> build(HttpStatus status, String message) {
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("timestamp", Instant.now().toString());
        body.put("status", status.value());
        body.put("error", status.getReasonPhrase());
        body.put("message", message);
        return ResponseEntity.status(status).body(body);
    }
}
