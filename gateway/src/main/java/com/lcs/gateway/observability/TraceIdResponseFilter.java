package com.lcs.gateway.observability;

import io.micrometer.tracing.Tracer;
import org.springframework.cloud.gateway.filter.GatewayFilterChain;
import org.springframework.cloud.gateway.filter.GlobalFilter;
import org.springframework.core.Ordered;
import org.springframework.stereotype.Component;
import org.springframework.web.server.ServerWebExchange;
import reactor.core.publisher.Mono;

/**
 * 응답에 현재 요청의 traceId를 실어 보낸다 (D-65).
 *
 * <p>추적 자체는 이미 되고 있었지만 traceId를 아는 방법이 로그를 뒤지는 것뿐이었다.
 * 그래서 "이 요청이 어디를 거쳤나"를 보려면 시각으로 로그를 찾아 traceId를 옮겨
 * 적은 뒤 Zipkin에 넣어야 했다. 헤더로 내려주면 호출한 쪽이 바로 알 수 있고,
 * 데모 콘솔은 그 값으로 Zipkin 링크를 만든다.
 *
 * <p>응답이 커밋되기 전에 넣어야 한다. 이미 나가기 시작한 응답의 헤더는 바꿀 수
 * 없어 조용히 무시된다 — 그래서 체인 실행 후가 아니라 {@code beforeCommit}에 건다.
 */
@Component
public class TraceIdResponseFilter implements GlobalFilter, Ordered {

    static final String TRACE_ID_HEADER = "X-Trace-Id";

    private final Tracer tracer;

    public TraceIdResponseFilter(Tracer tracer) {
        this.tracer = tracer;
    }

    @Override
    public Mono<Void> filter(ServerWebExchange exchange, GatewayFilterChain chain) {
        // Mono.defer로 감싸 구독 시점에 읽는다.
        //
        // beforeCommit 콜백 안에서 tracer.currentSpan()을 부르면 항상 null이다.
        // 그 콜백은 응답을 실제로 쓰는 시점에 리액티브 체인 밖에서 돌아
        // 컨텍스트 전파가 닿지 않기 때문이다. 처음에 그렇게 짰다가 헤더가
        // 조용히 안 붙는 것을 보고 고쳤다 — 예외도 나지 않아서 코드만 보면
        // 맞아 보인다.
        return Mono.defer(() -> {
            var span = tracer.currentSpan();
            if (span != null) {
                String traceId = span.context().traceId();
                exchange.getResponse().beforeCommit(() -> {
                    exchange.getResponse().getHeaders().set(TRACE_ID_HEADER, traceId);
                    return Mono.empty();
                });
            }
            return chain.filter(exchange);
        });
    }

    /**
     * 가장 먼저 돈다. 인증 실패(401)·서비스 토큰 발급 실패(503)처럼 체인 중간에서
     * 끊기는 응답에도 traceId가 붙어야 한다 — 오히려 그때가 추적이 더 필요하다.
     */
    @Override
    public int getOrder() {
        return Ordered.HIGHEST_PRECEDENCE;
    }
}
