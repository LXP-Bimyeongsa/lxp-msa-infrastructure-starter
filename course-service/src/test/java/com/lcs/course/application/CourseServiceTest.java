package com.lcs.course.application;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.BDDMockito.given;

import com.lcs.course.domain.Course;
import com.lcs.course.infrastructure.persistence.CourseRepository;
import com.lcs.course.infrastructure.storage.VideoStorage;
import java.util.HashMap;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.test.util.ReflectionTestUtils;

// Mongo 매핑이 아니라 도메인 규칙을 검증한다 — 소유권, 업로드 확인, 상태 전이.
// 실제 Mongo 저장은 E2E에서 컨테이너로 확인한다.
@ExtendWith(MockitoExtension.class)
class CourseServiceTest {

    @Mock
    private VideoStorage videoStorage;

    private CourseService courseService;
    private Map<String, Course> store;

    @BeforeEach
    void setUp() {
        store = new HashMap<>();
        courseService = new CourseService(new InMemoryCourseRepository(store), videoStorage);
    }

    @Test
    @DisplayName("강의를 생성하면 동영상은 아직 없는 상태다")
    void createStartsWithoutVideo() {
        Course course = courseService.create(1L, "MSA 입문", "사가와 아웃박스");

        assertThat(course.getInstructorId()).isEqualTo(1L);
        assertThat(course.isVideoUploaded()).isFalse();
    }

    @Test
    @DisplayName("업로드 URL을 발급하면 객체 키가 강의에 저장된다")
    void issueUploadUrlAssignsKey() {
        Course course = courseService.create(1L, "제목", "설명");
        given(videoStorage.newObjectKey(anyString())).willReturn("courses/x/abc.mp4");
        given(videoStorage.issueUploadUrl("courses/x/abc.mp4"))
                .willReturn(new VideoStorage.PresignedUrl("http://localhost:9000/signed", 600));

        VideoStorage.PresignedUrl url = courseService.issueUploadUrl(course.getId(), 1L);

        assertThat(url.url()).contains("signed");
        assertThat(courseService.findById(course.getId()).getVideoObjectKey())
                .isEqualTo("courses/x/abc.mp4");
    }

    @Test
    @DisplayName("남의 강의에는 업로드 URL을 발급하지 않는다 — 존재 여부도 숨긴다")
    void cannotIssueUrlForOthersCourse() {
        Course course = courseService.create(1L, "제목", "설명");

        assertThatThrownBy(() -> courseService.issueUploadUrl(course.getId(), 999L))
                .isInstanceOf(CourseNotFoundException.class);
    }

    @Test
    @DisplayName("객체가 실제로 없으면 완료 통지를 거부한다 — 클라이언트 말만 믿지 않는다")
    void completeRejectedWhenObjectMissing() {
        Course course = givenCourseWithUploadUrl("courses/x/abc.mp4");
        given(videoStorage.objectExists("courses/x/abc.mp4")).willReturn(false);

        assertThatThrownBy(() -> courseService.completeUpload(course.getId(), 1L))
                .isInstanceOf(VideoNotUploadedException.class);
        assertThat(courseService.findById(course.getId()).isVideoUploaded()).isFalse();
    }

    @Test
    @DisplayName("객체가 확인되면 완료 처리된다")
    void completeSucceedsWhenObjectExists() {
        Course course = givenCourseWithUploadUrl("courses/x/abc.mp4");
        given(videoStorage.objectExists("courses/x/abc.mp4")).willReturn(true);

        assertThat(courseService.completeUpload(course.getId(), 1L).isVideoUploaded()).isTrue();
    }

    @Test
    @DisplayName("업로드되지 않은 강의는 재생 URL을 주지 않는다")
    void noPlaybackUrlBeforeUpload() {
        Course course = courseService.create(1L, "제목", "설명");

        assertThatThrownBy(() -> courseService.issuePlaybackUrl(course.getId()))
                .isInstanceOf(VideoNotUploadedException.class);
    }

    @Test
    @DisplayName("URL을 재발급하면 업로드 완료 상태가 해제된다")
    void reissueResetsUploadedFlag() {
        Course course = givenCourseWithUploadUrl("courses/x/first.mp4");
        given(videoStorage.objectExists("courses/x/first.mp4")).willReturn(true);
        courseService.completeUpload(course.getId(), 1L);

        given(videoStorage.newObjectKey(anyString())).willReturn("courses/x/second.mp4");
        courseService.issueUploadUrl(course.getId(), 1L);

        // 키가 바뀌었는데 완료 상태를 그대로 두면 없는 파일의 재생 URL이 발급된다
        assertThat(courseService.findById(course.getId()).isVideoUploaded()).isFalse();
    }

    private Course givenCourseWithUploadUrl(String objectKey) {
        Course course = courseService.create(1L, "제목", "설명");
        given(videoStorage.newObjectKey(anyString())).willReturn(objectKey);
        given(videoStorage.issueUploadUrl(anyString()))
                .willReturn(new VideoStorage.PresignedUrl("http://localhost:9000/signed", 600));
        courseService.issueUploadUrl(course.getId(), 1L);
        return course;
    }

    // MongoRepository의 기본 메서드만 쓰는 최소 구현.
    // Mockito로 save/findById를 일일이 스텁하면 테스트가 저장소 흉내에 묻힌다.
    private static class InMemoryCourseRepository implements CourseRepository {

        private final Map<String, Course> store;

        InMemoryCourseRepository(Map<String, Course> store) {
            this.store = store;
        }

        @Override
        public <S extends Course> S save(S entity) {
            if (entity.getId() == null) {
                ReflectionTestUtils.setField(entity, "id", UUID.randomUUID().toString());
            }
            store.put(entity.getId(), entity);
            return entity;
        }

        @Override
        public Optional<Course> findById(String id) {
            return Optional.ofNullable(store.get(id));
        }

        @Override
        public java.util.List<Course> findByInstructorId(Long instructorId) {
            return store.values().stream()
                    .filter(c -> c.getInstructorId().equals(instructorId))
                    .toList();
        }

        // 아래는 이 테스트에서 쓰지 않는다.
        @Override public <S extends Course> java.util.List<S> saveAll(Iterable<S> e) { throw new UnsupportedOperationException(); }
        @Override public java.util.List<Course> findAll() { return java.util.List.copyOf(store.values()); }
        @Override public java.util.List<Course> findAllById(Iterable<String> ids) { throw new UnsupportedOperationException(); }
        @Override public boolean existsById(String id) { return store.containsKey(id); }
        @Override public long count() { return store.size(); }
        @Override public void deleteById(String id) { store.remove(id); }
        @Override public void delete(Course entity) { store.remove(entity.getId()); }
        @Override public void deleteAllById(Iterable<? extends String> ids) { throw new UnsupportedOperationException(); }
        @Override public void deleteAll(Iterable<? extends Course> entities) { throw new UnsupportedOperationException(); }
        @Override public void deleteAll() { store.clear(); }
        @Override public java.util.List<Course> findAll(org.springframework.data.domain.Sort sort) { throw new UnsupportedOperationException(); }
        @Override public org.springframework.data.domain.Page<Course> findAll(org.springframework.data.domain.Pageable p) { throw new UnsupportedOperationException(); }
        @Override public <S extends Course> S insert(S entity) { return save(entity); }
        @Override public <S extends Course> java.util.List<S> insert(Iterable<S> e) { throw new UnsupportedOperationException(); }
        @Override public <S extends Course> Optional<S> findOne(org.springframework.data.domain.Example<S> ex) { throw new UnsupportedOperationException(); }
        @Override public <S extends Course> java.util.List<S> findAll(org.springframework.data.domain.Example<S> ex) { throw new UnsupportedOperationException(); }
        @Override public <S extends Course> java.util.List<S> findAll(org.springframework.data.domain.Example<S> ex, org.springframework.data.domain.Sort sort) { throw new UnsupportedOperationException(); }
        @Override public <S extends Course> org.springframework.data.domain.Page<S> findAll(org.springframework.data.domain.Example<S> ex, org.springframework.data.domain.Pageable p) { throw new UnsupportedOperationException(); }
        @Override public <S extends Course> long count(org.springframework.data.domain.Example<S> ex) { throw new UnsupportedOperationException(); }
        @Override public <S extends Course> boolean exists(org.springframework.data.domain.Example<S> ex) { throw new UnsupportedOperationException(); }
        @Override public <S extends Course, R> R findBy(org.springframework.data.domain.Example<S> ex, java.util.function.Function<org.springframework.data.repository.query.FluentQuery.FetchableFluentQuery<S>, R> fn) { throw new UnsupportedOperationException(); }
    }
}
