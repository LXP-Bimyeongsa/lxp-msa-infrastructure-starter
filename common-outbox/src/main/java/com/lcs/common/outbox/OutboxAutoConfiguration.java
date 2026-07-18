package com.lcs.common.outbox;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.autoconfigure.AutoConfiguration;
import org.springframework.boot.autoconfigure.AutoConfigurationPackage;
import org.springframework.boot.autoconfigure.condition.ConditionalOnMissingBean;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.boot.autoconfigure.data.jpa.JpaRepositoriesAutoConfiguration;
import org.springframework.boot.autoconfigure.orm.jpa.HibernateJpaAutoConfiguration;
import org.springframework.context.annotation.Bean;

/**
 * Outbox 구성요소를 소비 서비스에 자동 등록한다 (D-30).
 *
 * <p>소비 서비스의 {@code @SpringBootApplication}은 자기 패키지(예: {@code com.lcs.payment})만
 * 스캔하므로 {@code com.lcs.common.outbox}의 빈·엔티티·리포지토리가 잡히지 않는다.
 * 각 서비스에 {@code @EntityScan}/{@code @EnableJpaRepositories}를 직접 붙이는 방법도 있지만,
 * 그 두 애노테이션은 Boot의 기본 스캔 패키지를 <b>대체</b>해버려 서비스 자신의 엔티티가
 * 사라진다. 그래서 기본 패키지에 <b>덧붙이는</b> {@code @AutoConfigurationPackage}를 쓴다.
 *
 * <p>{@code before}로 JPA 자동설정보다 먼저 돌게 하는 이유 — JPA 자동설정이
 * 자동설정 패키지 목록을 읽는 시점에 이미 이 패키지가 등록돼 있어야 한다.
 */
@AutoConfiguration(before = { JpaRepositoriesAutoConfiguration.class, HibernateJpaAutoConfiguration.class })
@AutoConfigurationPackage
public class OutboxAutoConfiguration {

    @Bean
    @ConditionalOnMissingBean
    public OutboxWriter outboxWriter(OutboxRepository outboxRepository, ObjectMapper objectMapper) {
        return new OutboxWriter(outboxRepository, objectMapper);
    }

    /**
     * 릴레이는 발행 측에만 필요하다. 이벤트를 소비만 하는 서비스는
     * {@code outbox.relay.enabled=false}로 끌 수 있다.
     */
    @Bean
    @ConditionalOnMissingBean
    @ConditionalOnProperty(name = "outbox.relay.enabled", havingValue = "true", matchIfMissing = true)
    public OutboxRelay outboxRelay(OutboxRepository outboxRepository,
                                   RabbitTemplate rabbitTemplate,
                                   @Value("${outbox.relay.exchange}") String exchange) {
        return new OutboxRelay(outboxRepository, rabbitTemplate, exchange);
    }
}
