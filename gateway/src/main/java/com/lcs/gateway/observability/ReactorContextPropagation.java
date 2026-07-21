package com.lcs.gateway.observability;

import jakarta.annotation.PostConstruct;
import org.springframework.context.annotation.Configuration;
import reactor.core.publisher.Hooks;

/**
 * 리액터 연산자 안에서도 추적 컨텍스트를 ThreadLocal로 복원한다 (D-65).
 *
 * <p>이것이 없으면 {@code Tracer.currentSpan()}이 GlobalFilter 안에서 항상 null이다.
 * WebFlux는 스팬을 Reactor 컨텍스트에 담아 나르는데, ThreadLocal 기반 API는 그것을
 * 보지 못한다. 예외가 나지 않고 조용히 null이라 코드만 보면 맞아 보인다 —
 * 실제로 그렇게 두 번 헛짚었다.
 *
 * <p>전역 훅이라 이 애플리케이션의 모든 리액티브 체인에 걸린다. 컨텍스트를 복원하는
 * 비용이 붙지만, gateway는 이미 요청마다 JWKS 검증과 introspection(D-35)을 하고
 * 있어 그에 비하면 작다. 여기서만 켜는 이유도 같다 — 다운스트림 서비스들은
 * 이 값이 필요 없어 비용만 늘어난다.
 */
@Configuration
public class ReactorContextPropagation {

    @PostConstruct
    void enable() {
        Hooks.enableAutomaticContextPropagation();
    }
}
