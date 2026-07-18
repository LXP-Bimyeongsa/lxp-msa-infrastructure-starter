package com.lcs.course.domain;

import java.time.Instant;
import org.springframework.data.annotation.Id;
import org.springframework.data.mongodb.core.mapping.Document;
import org.springframework.data.mongodb.core.index.Indexed;

// 강의 메타데이터만 보관한다. 동영상 원본은 MinIO에 있고 여기엔 객체 키만 둔다 (D-07).
@Document(collection = "course")
public class Course {

    @Id
    private String id;

    private String title;

    private String description;

    @Indexed
    private Long instructorId;

    // MinIO 객체 키. 서버가 생성하며 클라이언트 입력을 그대로 쓰지 않는다.
    private String videoObjectKey;

    // 업로드 완료가 실제로 확인된 경우에만 true. 클라이언트 통지만으로는 바뀌지 않는다.
    private boolean videoUploaded;

    private Instant createdAt;

    protected Course() {
        // Spring Data 전용
    }

    private Course(String title, String description, Long instructorId) {
        this.title = title;
        this.description = description;
        this.instructorId = instructorId;
        this.videoUploaded = false;
        this.createdAt = Instant.now();
    }

    public static Course create(String title, String description, Long instructorId) {
        return new Course(title, description, instructorId);
    }

    public void assignVideoObjectKey(String objectKey) {
        this.videoObjectKey = objectKey;
        // 키를 새로 발급하면 아직 올라오지 않은 상태로 되돌린다.
        this.videoUploaded = false;
    }

    public void markVideoUploaded() {
        this.videoUploaded = true;
    }

    public boolean isOwnedBy(Long memberId) {
        return this.instructorId.equals(memberId);
    }

    public boolean hasVideo() {
        return videoUploaded && videoObjectKey != null;
    }

    public String getId() {
        return id;
    }

    public String getTitle() {
        return title;
    }

    public String getDescription() {
        return description;
    }

    public Long getInstructorId() {
        return instructorId;
    }

    public String getVideoObjectKey() {
        return videoObjectKey;
    }

    public boolean isVideoUploaded() {
        return videoUploaded;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }
}
