package com.lcs.member.presentation;

import com.lcs.member.application.DuplicateEmailException;
import com.lcs.member.application.MemberNotFoundException;
import com.lcs.member.infrastructure.keycloak.KeycloakUserCreationException;
import java.time.Instant;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import java.util.LinkedHashMap;
import java.util.Map;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

@RestControllerAdvice
public class ApiExceptionHandler {

    private static final Logger log = LoggerFactory.getLogger(ApiExceptionHandler.class);

    @ExceptionHandler(DuplicateEmailException.class)
    public ResponseEntity<Map<String, Object>> handleDuplicateEmail(DuplicateEmailException e) {
        return build(HttpStatus.CONFLICT, e.getMessage());
    }

    @ExceptionHandler(MemberNotFoundException.class)
    public ResponseEntity<Map<String, Object>> handleNotFound(MemberNotFoundException e) {
        return build(HttpStatus.NOT_FOUND, e.getMessage());
    }

    @ExceptionHandler(KeycloakUserCreationException.class)
    public ResponseEntity<Map<String, Object>> handleKeycloak(KeycloakUserCreationException e) {
        // 원인을 로그로 남긴다. 클라이언트에는 내부 사정을 노출하지 않는다.
        log.error("Keycloak 연동 실패", e);
        return build(HttpStatus.SERVICE_UNAVAILABLE, "가입 처리를 완료할 수 없습니다. 잠시 후 다시 시도해 주세요.");
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<Map<String, Object>> handleValidation(MethodArgumentNotValidException e) {
        String detail = e.getBindingResult().getFieldErrors().stream()
                .map(f -> f.getField() + ": " + f.getDefaultMessage())
                .reduce((a, b) -> a + ", " + b)
                .orElse("잘못된 요청입니다.");
        return build(HttpStatus.BAD_REQUEST, detail);
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
