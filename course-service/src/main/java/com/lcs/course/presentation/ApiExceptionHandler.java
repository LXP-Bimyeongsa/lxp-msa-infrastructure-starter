package com.lcs.course.presentation;

import com.lcs.course.application.CourseNotFoundException;
import com.lcs.course.application.VideoNotUploadedException;
import com.lcs.course.infrastructure.storage.StorageUnavailableException;
import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.Map;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.MissingRequestHeaderException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

@RestControllerAdvice
public class ApiExceptionHandler {

    private static final Logger log = LoggerFactory.getLogger(ApiExceptionHandler.class);

    @ExceptionHandler(CourseNotFoundException.class)
    public ResponseEntity<Map<String, Object>> handleNotFound(CourseNotFoundException e) {
        return build(HttpStatus.NOT_FOUND, e.getMessage());
    }

    @ExceptionHandler(VideoNotUploadedException.class)
    public ResponseEntity<Map<String, Object>> handleVideoMissing(VideoNotUploadedException e) {
        return build(HttpStatus.CONFLICT, e.getMessage());
    }

    @ExceptionHandler(StorageUnavailableException.class)
    public ResponseEntity<Map<String, Object>> handleStorage(StorageUnavailableException e) {
        // 원인을 로그에 남긴다. 클라이언트에는 내부 사정을 노출하지 않지만,
        // 서버 로그에도 없으면 장애 원인을 추적할 수 없다.
        log.error("스토리지 오류", e);
        return build(HttpStatus.SERVICE_UNAVAILABLE, "스토리지를 사용할 수 없습니다.");
    }

    @ExceptionHandler(MissingRequestHeaderException.class)
    public ResponseEntity<Map<String, Object>> handleMissingHeader(MissingRequestHeaderException e) {
        return build(HttpStatus.UNAUTHORIZED, "인증 정보가 없습니다.");
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
