package com.lcs.course.presentation;

import com.lcs.course.application.CourseService;
import com.lcs.course.domain.Course;
import com.lcs.course.infrastructure.storage.VideoStorage;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import java.time.Instant;
import java.util.Map;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/courses")
public class CourseController {

    private final CourseService courseService;

    public CourseController(CourseService courseService) {
        this.courseService = courseService;
    }

    @GetMapping("/ping")
    public Map<String, Object> ping() {
        return Map.of(
                "service", "course-service",
                "status", "UP",
                "timestamp", Instant.now().toString()
        );
    }

    // instructorId는 body가 아니라 gateway가 JWT에서 넣어준 X-Member-Id에서 받는다.
    @PostMapping
    public ResponseEntity<CourseResponse> create(
            @RequestHeader("X-Member-Id") Long instructorId,
            @Valid @RequestBody CreateRequest request) {
        Course course = courseService.create(instructorId, request.title(), request.description());
        return ResponseEntity.status(HttpStatus.CREATED).body(CourseResponse.from(course));
    }

    @GetMapping("/{courseId}")
    public CourseResponse find(@PathVariable String courseId) {
        return CourseResponse.from(courseService.findById(courseId));
    }

    /** 업로드용 서명 URL. 클라이언트가 이 URL로 MinIO에 직접 PUT 한다 (D-07). */
    @PostMapping("/{courseId}/video/upload-url")
    public PresignedUrlResponse issueUploadUrl(
            @RequestHeader("X-Member-Id") Long memberId,
            @PathVariable String courseId) {
        return PresignedUrlResponse.from(courseService.issueUploadUrl(courseId, memberId));
    }

    /** 업로드 완료 통지. 서버가 객체 존재를 확인한 뒤에만 완료 처리한다. */
    @PostMapping("/{courseId}/video/complete")
    public CourseResponse completeUpload(
            @RequestHeader("X-Member-Id") Long memberId,
            @PathVariable String courseId) {
        return CourseResponse.from(courseService.completeUpload(courseId, memberId));
    }

    /** 재생용 서명 URL. 활성 구독이 있어야 발급된다 (D-36). */
    @GetMapping("/{courseId}/video/playback-url")
    public PresignedUrlResponse issuePlaybackUrl(
            @RequestHeader("X-Member-Id") Long memberId,
            @PathVariable String courseId) {
        return PresignedUrlResponse.from(courseService.issuePlaybackUrl(courseId, memberId));
    }

    public record CreateRequest(
            @NotBlank @Size(max = 200) String title,
            @Size(max = 2000) String description
    ) {
    }

    public record CourseResponse(
            String courseId,
            String title,
            String description,
            Long instructorId,
            boolean videoUploaded,
            Instant createdAt
    ) {
        // 객체 키는 응답에 담지 않는다. 클라이언트는 서명 URL만 알면 된다.
        static CourseResponse from(Course course) {
            return new CourseResponse(
                    course.getId(),
                    course.getTitle(),
                    course.getDescription(),
                    course.getInstructorId(),
                    course.isVideoUploaded(),
                    course.getCreatedAt()
            );
        }
    }

    public record PresignedUrlResponse(String url, int expiresInSeconds) {
        static PresignedUrlResponse from(VideoStorage.PresignedUrl presigned) {
            return new PresignedUrlResponse(presigned.url(), presigned.expiresInSeconds());
        }
    }
}
