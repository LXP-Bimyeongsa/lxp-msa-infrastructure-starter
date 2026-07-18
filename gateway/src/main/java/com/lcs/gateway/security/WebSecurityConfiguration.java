package com.lcs.gateway.security;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.config.annotation.web.reactive.EnableWebFluxSecurity;
import org.springframework.security.config.web.server.ServerHttpSecurity;
import org.springframework.security.web.server.SecurityWebFilterChain;

// oauth2-resource-server 의존성이 들어오면서 Spring Security가
// 기본적으로 모든 경로를 막는다. 인증 판단은 JwtAuthenticationFilter가
// 이미 하고 있으므로(공개 경로 규칙 포함) 여기서는 통과시킨다.
//
// 두 곳에서 인증을 하면 규칙이 갈라져 "어디서 막혔는지" 추적이 어려워진다.
// 판단 지점을 한 곳에 모으는 편이 낫다.
@Configuration
@EnableWebFluxSecurity
public class WebSecurityConfiguration {

    @Bean
    public SecurityWebFilterChain springSecurityFilterChain(ServerHttpSecurity http) {
        return http
                .csrf(ServerHttpSecurity.CsrfSpec::disable)
                .httpBasic(ServerHttpSecurity.HttpBasicSpec::disable)
                .formLogin(ServerHttpSecurity.FormLoginSpec::disable)
                .authorizeExchange(exchange -> exchange.anyExchange().permitAll())
                .build();
    }
}
