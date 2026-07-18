package com.lcs.subscription.infrastructure.grpc;

import io.github.resilience4j.circuitbreaker.CircuitBreakerConfig;
import io.github.resilience4j.timelimiter.TimeLimiterConfig;
import java.time.Duration;
import org.springframework.cloud.circuitbreaker.resilience4j.Resilience4JCircuitBreakerFactory;
import org.springframework.cloud.client.circuitbreaker.Customizer;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class CircuitBreakerConfiguration {

    @Bean
    public Customizer<Resilience4JCircuitBreakerFactory> memberServiceCircuitBreaker() {
        CircuitBreakerConfig config = CircuitBreakerConfig.custom()
                // 최근 10회 중 50% 이상 실패하면 개방
                .slidingWindowType(CircuitBreakerConfig.SlidingWindowType.COUNT_BASED)
                .slidingWindowSize(10)
                .minimumNumberOfCalls(5)
                .failureRateThreshold(50.0f)
                // 개방 후 10초 뒤 반개방으로 전환해 3회만 시험 호출
                .waitDurationInOpenState(Duration.ofSeconds(10))
                .permittedNumberOfCallsInHalfOpenState(3)
                .automaticTransitionFromOpenToHalfOpenEnabled(true)
                // "회원 없음"은 원격이 정상 동작한 결과다. 실패로 세면
                // 잘못된 요청이 몰릴 때 멀쩡한 서비스의 서킷이 열린다.
                .ignoreExceptions(MemberNotFoundOnRemoteException.class)
                .build();

        return factory -> factory.configure(builder -> builder
                        .circuitBreakerConfig(config)
                        // gRPC deadline(2s)보다 약간 길게 — 데드라인이 먼저 걸리게 둔다
                        .timeLimiterConfig(TimeLimiterConfig.custom()
                                .timeoutDuration(Duration.ofSeconds(3))
                                .build()),
                "member-service");
    }
}
