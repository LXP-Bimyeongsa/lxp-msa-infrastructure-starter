package com.lcs.course.infrastructure.storage;

import io.minio.MinioClient;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

// MinIO 클라이언트를 두 개 둔다. 이유가 presigned URL의 동작 방식에 있다.
//
// presigned URL은 "호스트를 포함해" 서명된다. 내부 주소(minio:9000)로 서명하면
// 그 URL은 도커 네트워크 밖에서 열 수 없고, 브라우저가 호스트만 바꿔 접속하면
// 서명이 깨져 SignatureDoesNotMatch가 난다.
//
// 그래서 URL 발급은 "클라이언트가 실제로 접속할 주소"로 서명해야 하고,
// 서버 자신이 하는 작업(객체 존재 확인 등)은 내부 주소로 해야 빠르고 안전하다.
@Configuration
public class MinioConfiguration {

    /** 서버 → MinIO 직접 호출용 (statObject 등). 도커 네트워크 내부 주소. */
    @Bean
    public MinioClient internalMinioClient(
            @Value("${minio.internal-endpoint}") String endpoint,
            @Value("${minio.access-key}") String accessKey,
            @Value("${minio.secret-key}") String secretKey,
            @Value("${minio.region:us-east-1}") String region) {
        return MinioClient.builder()
                .endpoint(endpoint)
                .credentials(accessKey, secretKey)
                .region(region)
                .build();
    }

    /**
     * presigned URL 서명 전용. 클라이언트가 접속할 외부 주소로 서명한다.
     *
     * region을 반드시 지정해야 한다. 지정하지 않으면 SDK가 서명 전에
     * 버킷 리전을 물어보려고 endpoint로 실제 네트워크 호출을 하는데,
     * 이 endpoint는 "컨테이너 밖에서 보이는 주소"라 서버 자신은 접속할 수 없다.
     * (localhost:9000으로 나가서 Connection refused)
     */
    @Bean
    public MinioClient presignMinioClient(
            @Value("${minio.public-endpoint}") String endpoint,
            @Value("${minio.access-key}") String accessKey,
            @Value("${minio.secret-key}") String secretKey,
            @Value("${minio.region:us-east-1}") String region) {
        return MinioClient.builder()
                .endpoint(endpoint)
                .credentials(accessKey, secretKey)
                .region(region)
                .build();
    }
}
