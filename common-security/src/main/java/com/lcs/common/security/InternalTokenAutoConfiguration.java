package com.lcs.common.security;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.autoconfigure.AutoConfiguration;
import org.springframework.boot.autoconfigure.condition.ConditionalOnMissingBean;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.boot.web.client.RestTemplateBuilder;
import org.springframework.context.annotation.Bean;
import org.springframework.http.HttpStatus;
import org.springframework.security.config.Customizer;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.oauth2.core.DelegatingOAuth2TokenValidator;
import org.springframework.security.oauth2.jwt.JwtDecoder;
import org.springframework.security.oauth2.jwt.JwtValidators;
import org.springframework.security.oauth2.jwt.NimbusJwtDecoder;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.authentication.HttpStatusEntryPoint;

/**
 * 다운스트림 서비스를 resource server로 만든다 (D-33).
 *
 * <p>지금까지 서비스들은 {@code X-Member-Id} 헤더를 무조건 신뢰했다. gateway가
 * 검증 후 주입한다는 전제였지만, 네트워크에 닿을 수 있으면 누구나 gateway를
 * 건너뛰고 그 헤더를 직접 보낼 수 있었다(P-11).
 *
 * <p>이제 gateway가 붙인 서비스 토큰을 요구한다. 헤더는 계속 신뢰하되,
 * 그 헤더를 실어 온 요청이 gateway를 거쳤다는 것은 토큰이 증명한다.
 */
@AutoConfiguration
@EnableWebSecurity
public class InternalTokenAutoConfiguration {

    /**
     * {@code issuer-uri}가 아니라 {@code jwk-set-uri}로 설정하는 이유 (P-09) —
     * issuer-uri를 주면 Spring이 그 주소로 OIDC 디스커버리 문서를 가져오려 한다.
     * issuer는 토큰에 박히는 <b>외부</b> 주소(localhost:8180)라 컨테이너 안에서는
     * 자기 자신을 가리켜 기동이 실패한다. 실제 통신은 내부 주소로 하고
     * issuer는 문자열 비교만 한다.
     */
    @Bean
    @ConditionalOnMissingBean
    public JwtDecoder jwtDecoder(@Value("${internal-auth.jwk-set-uri}") String jwkSetUri,
                                 @Value("${internal-auth.issuer-uri}") String issuerUri,
                                 @Value("${internal-auth.audience:lxp-internal}") String audience) {

        NimbusJwtDecoder decoder = NimbusJwtDecoder.withJwkSetUri(jwkSetUri).build();
        decoder.setJwtValidator(new DelegatingOAuth2TokenValidator<>(
                JwtValidators.createDefaultWithIssuer(issuerUri),
                new InternalAudienceValidator(audience)));
        return decoder;
    }

    /**
     * 다른 서비스를 호출하는 서비스만 필요하다 (D-34).
     * {@code internal-auth.client.client-id}가 설정된 경우에만 만든다 —
     * 호출하지 않는 서비스에까지 client secret을 쥐여줄 이유가 없다.
     */
    @Bean
    @ConditionalOnMissingBean
    @ConditionalOnProperty(name = "internal-auth.client.client-id")
    public ServiceAccountTokenClient serviceAccountTokenClient(
            RestTemplateBuilder builder,
            @Value("${internal-auth.client.token-uri}") String tokenUri,
            @Value("${internal-auth.client.client-id}") String clientId,
            @Value("${internal-auth.client.client-secret}") String clientSecret) {
        return new ServiceAccountTokenClient(builder.build(), tokenUri, clientId, clientSecret);
    }

    @Bean
    @ConditionalOnMissingBean
    public SecurityFilterChain internalTokenFilterChain(HttpSecurity http, JwtDecoder jwtDecoder)
            throws Exception {
        return http
                .csrf(csrf -> csrf.disable())
                .httpBasic(basic -> basic.disable())
                .formLogin(form -> form.disable())
                .sessionManagement(s -> s.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
                .authorizeHttpRequests(auth -> auth
                        // 헬스체크와 메트릭은 토큰 없이 열어둔다. compose healthcheck와
                        // Prometheus 스크레이프가 토큰을 들고 오지 않는다.
                        .requestMatchers("/actuator/**").permitAll()
                        .anyRequest().authenticated())
                .oauth2ResourceServer(oauth2 -> oauth2.jwt(Customizer.withDefaults()))
                // 인증 실패는 401로 끝낸다. 기본 동작은 WWW-Authenticate 협상이라
                // API 클라이언트에게는 잡음이다.
                .exceptionHandling(e -> e.authenticationEntryPoint(
                        new HttpStatusEntryPoint(HttpStatus.UNAUTHORIZED)))
                .build();
    }
}
