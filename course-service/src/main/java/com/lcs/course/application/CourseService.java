package com.lcs.course.application;

import com.lcs.course.domain.Course;
import com.lcs.course.infrastructure.persistence.CourseRepository;
import com.lcs.course.infrastructure.storage.VideoStorage;
import java.util.List;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

@Service
public class CourseService {

    private static final Logger log = LoggerFactory.getLogger(CourseService.class);

    private final CourseRepository courseRepository;
    private final VideoStorage videoStorage;

    public CourseService(CourseRepository courseRepository, VideoStorage videoStorage) {
        this.courseRepository = courseRepository;
        this.videoStorage = videoStorage;
    }

    public Course create(Long instructorId, String title, String description) {
        return courseRepository.save(Course.create(title, description, instructorId));
    }

    public Course findById(String courseId) {
        return courseRepository.findById(courseId)
                .orElseThrow(() -> new CourseNotFoundException(courseId));
    }

    public List<Course> findByInstructor(Long instructorId) {
        return courseRepository.findByInstructorId(instructorId);
    }

    /** 업로드용 서명 URL 발급. 소유자만 가능하다. */
    public VideoStorage.PresignedUrl issueUploadUrl(String courseId, Long requesterId) {
        Course course = findOwned(courseId, requesterId);
        String objectKey = videoStorage.newObjectKey(courseId);
        course.assignVideoObjectKey(objectKey);
        courseRepository.save(course);
        return videoStorage.issueUploadUrl(objectKey);
    }

    /**
     * 업로드 완료 처리. 클라이언트 통지를 그대로 믿지 않고
     * MinIO에 객체가 실제로 있는지 확인한 뒤에만 완료로 표시한다.
     */
    public Course completeUpload(String courseId, Long requesterId) {
        Course course = findOwned(courseId, requesterId);
        if (course.getVideoObjectKey() == null) {
            throw new VideoNotUploadedException(courseId);
        }
        if (!videoStorage.objectExists(course.getVideoObjectKey())) {
            log.warn("업로드 완료 통지를 받았으나 객체가 없음: courseId={} key={}",
                    courseId, course.getVideoObjectKey());
            throw new VideoNotUploadedException(courseId);
        }
        course.markVideoUploaded();
        return courseRepository.save(course);
    }

    /** 재생용 서명 URL 발급. 업로드가 확인된 강의만 발급한다. */
    public VideoStorage.PresignedUrl issuePlaybackUrl(String courseId) {
        Course course = findById(courseId);
        if (!course.hasVideo()) {
            throw new VideoNotUploadedException(courseId);
        }
        return videoStorage.issuePlaybackUrl(course.getVideoObjectKey());
    }

    private Course findOwned(String courseId, Long memberId) {
        Course course = findById(courseId);
        if (!course.isOwnedBy(memberId)) {
            // 소유자가 아니면 존재 여부도 숨긴다.
            throw new CourseNotFoundException(courseId);
        }
        return course;
    }
}
