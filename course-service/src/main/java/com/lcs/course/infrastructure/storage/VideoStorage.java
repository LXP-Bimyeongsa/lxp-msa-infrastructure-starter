package com.lcs.course.infrastructure.storage;

import io.minio.GetPresignedObjectUrlArgs;
import io.minio.MinioClient;
import io.minio.StatObjectArgs;
import io.minio.errors.ErrorResponseException;
import io.minio.http.Method;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.TimeUnit;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

// 동영상 원본은 클라이언트가 MinIO와 직접 주고받는다 (D-07).
// 이 서비스는 서명된 URL을 발급하고 업로드 여부를 확인할 뿐,
// 파일 바이트가 JVM을 통과하지 않는다.
@Component
public class VideoStorage {

    private static final Logger log = LoggerFactory.getLogger(VideoStorage.class);

    // "객체가 없다"는 뜻의 응답 코드. 이것만 정상적인 답으로 다루고 나머지는 장애다.
    // NoSuchObject는 일부 S3 호환 구현이 NoSuchKey 대신 쓴다.
    private static final Set<String> OBJECT_ABSENT_CODES = Set.of("NoSuchKey", "NoSuchObject");

    private final MinioClient internalClient;
    private final MinioClient presignClient;
    private final String bucket;
    private final int uploadUrlTtlSeconds;
    private final int playbackUrlTtlSeconds;

    public VideoStorage(@Qualifier("internalMinioClient") MinioClient internalClient,
                        @Qualifier("presignMinioClient") MinioClient presignClient,
                        @Value("${minio.bucket}") String bucket,
                        @Value("${minio.upload-url-ttl-seconds:600}") int uploadUrlTtlSeconds,
                        @Value("${minio.playback-url-ttl-seconds:3600}") int playbackUrlTtlSeconds) {
        this.internalClient = internalClient;
        this.presignClient = presignClient;
        this.bucket = bucket;
        this.uploadUrlTtlSeconds = uploadUrlTtlSeconds;
        this.playbackUrlTtlSeconds = playbackUrlTtlSeconds;
    }

    /**
     * 객체 키는 서버가 만든다. 클라이언트가 준 파일명을 그대로 키로 쓰면
     * 경로 조작으로 남의 객체를 덮어쓸 수 있다.
     */
    public String newObjectKey(String courseId) {
        return "courses/" + courseId + "/" + UUID.randomUUID() + ".mp4";
    }

    public PresignedUrl issueUploadUrl(String objectKey) {
        return new PresignedUrl(
                presign(Method.PUT, objectKey, uploadUrlTtlSeconds),
                uploadUrlTtlSeconds);
    }

    public PresignedUrl issuePlaybackUrl(String objectKey) {
        return new PresignedUrl(
                presign(Method.GET, objectKey, playbackUrlTtlSeconds),
                playbackUrlTtlSeconds);
    }

    /**
     * 객체가 실제로 올라왔는지 확인한다.
     * 클라이언트의 "업로드 끝났다"는 통지만 믿으면 파일 없이도 완료 처리가 된다.
     */
    public boolean objectExists(String objectKey) {
        try {
            internalClient.statObject(StatObjectArgs.builder()
                    .bucket(bucket)
                    .object(objectKey)
                    .build());
            return true;
        } catch (ErrorResponseException e) {
            // ErrorResponseException은 "객체 없음"만이 아니라 MinIO가 돌려주는
            // 모든 에러 응답(AccessDenied·NoSuchBucket·SignatureDoesNotMatch 등)을
            // 포괄한다. 전부 false로 돌리면 설정 오류가 "사용자가 업로드를 안 했다"로
            // 표시되고(409), 원인은 어디에도 남지 않는다.
            //
            // 그래서 코드를 보고 "정상적인 답"과 "장애"를 가른다.
            String code = e.errorResponse() == null ? null : e.errorResponse().code();
            if (OBJECT_ABSENT_CODES.contains(code)) {
                // 객체 없음 — 장애가 아니라 정상적인 답이다
                return false;
            }
            log.error("MinIO 객체 확인 실패: objectKey={} code={}", objectKey, code, e);
            throw new StorageUnavailableException("MinIO 객체 확인 실패: " + objectKey, e);
        } catch (Exception e) {
            throw new StorageUnavailableException("MinIO 객체 확인 실패: " + objectKey, e);
        }
    }

    private String presign(Method method, String objectKey, int ttlSeconds) {
        try {
            return presignClient.getPresignedObjectUrl(GetPresignedObjectUrlArgs.builder()
                    .method(method)
                    .bucket(bucket)
                    .object(objectKey)
                    .expiry(ttlSeconds, TimeUnit.SECONDS)
                    .build());
        } catch (Exception e) {
            throw new StorageUnavailableException("presigned URL 발급 실패: " + objectKey, e);
        }
    }

    public record PresignedUrl(String url, int expiresInSeconds) {
    }
}
