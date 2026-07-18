package com.lcs.course.presentation;

import java.time.Instant;
import java.util.Map;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/courses")
public class CourseController {

    @GetMapping("/ping")
    public Map<String, Object> ping() {
        return Map.of(
                "service", "course-service",
                "status", "UP",
                "timestamp", Instant.now().toString()
        );
    }
}
