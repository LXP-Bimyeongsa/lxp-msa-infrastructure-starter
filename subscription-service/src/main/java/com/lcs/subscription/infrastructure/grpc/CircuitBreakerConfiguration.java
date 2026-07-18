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
                // 둘 다 "원격이 요청을 받아 판단한 결과"다 — 원격이 살아 있다는 증거이므로
                // 서킷 집계에서 뺀다. 실패로 세면 멀쩡한 서비스의 서킷이 열리고,
                // 진짜 원인(잘못된 요청 / 우리 쪽 자격증명)이 서킷 로그에 묻힌다.
                //   - 회원 없음: 잘못된 요청이 몰릴 때 (D-17)
                //   - 자격증명 거절: 시크릿 설정이 틀렸을 때 (D-34)
                // 집계에서 뺄 뿐, 결과는 여전히 fail-closed다 — 확인 못 한 구독은 만들지 않는다.
                .ignoreExceptions(
                        MemberNotFoundOnRemoteException.class,
                        MemberCallRejectedException.class)
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
