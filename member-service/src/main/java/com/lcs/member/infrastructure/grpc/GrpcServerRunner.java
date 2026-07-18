package com.lcs.member.infrastructure.grpc;

import io.grpc.Server;
import io.grpc.ServerBuilder;
import jakarta.annotation.PreDestroy;
import java.io.IOException;
import java.util.concurrent.TimeUnit;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.stereotype.Component;

// gRPC 서버를 HTTP 서버와 별도 포트로 띄운다.
// 포트는 Consul 메타데이터로 등록되어 호출 측이 찾아온다.
@Component
public class GrpcServerRunner {

    private static final Logger log = LoggerFactory.getLogger(GrpcServerRunner.class);

    private final MemberQueryGrpcService memberQueryGrpcService;
    private final ServiceTokenServerInterceptor serviceTokenInterceptor;
    private final int port;
    private Server server;

    public GrpcServerRunner(MemberQueryGrpcService memberQueryGrpcService,
                            ServiceTokenServerInterceptor serviceTokenInterceptor,
                            @Value("${grpc.server.port:9092}") int port) {
        this.memberQueryGrpcService = memberQueryGrpcService;
        this.serviceTokenInterceptor = serviceTokenInterceptor;
        this.port = port;
    }

    @EventListener(ApplicationReadyEvent.class)
    public void start() throws IOException {
        server = ServerBuilder.forPort(port)
                // 서비스 토큰 검증 (D-34). 인터셉터를 서비스에 붙이지 않고 서버에 붙인다 —
                // 나중에 서비스가 추가돼도 인증이 빠지는 일이 없다.
                .intercept(serviceTokenInterceptor)
                .addService(memberQueryGrpcService)
                .build()
                .start();
        log.info("gRPC 서버 기동: port={} (서비스 토큰 필수)", port);
    }

    @PreDestroy
    public void stop() throws InterruptedException {
        if (server != null) {
            // 진행 중인 호출이 끝날 시간을 준 뒤 종료한다.
            server.shutdown().awaitTermination(5, TimeUnit.SECONDS);
            log.info("gRPC 서버 종료");
        }
    }
}
