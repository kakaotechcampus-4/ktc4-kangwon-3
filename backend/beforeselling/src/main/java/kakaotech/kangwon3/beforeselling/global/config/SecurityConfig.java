package kakaotech.kangwon3.beforeselling.global.config;

import kakaotech.kangwon3.beforeselling.global.config.properties.AppProperties;
import kakaotech.kangwon3.beforeselling.global.security.filter.JwtAuthenticationFilter;
import kakaotech.kangwon3.beforeselling.global.security.filter.JwtExceptionFilter;
import kakaotech.kangwon3.beforeselling.global.security.handler.CustomAccessDeniedHandler;
import kakaotech.kangwon3.beforeselling.global.security.handler.CustomAuthenticationEntryPoint;
import kakaotech.kangwon3.beforeselling.global.security.jwt.JwtProvider;
import kakaotech.kangwon3.beforeselling.global.security.oauth2.CustomOAuth2UserService;
import kakaotech.kangwon3.beforeselling.global.security.oauth2.handler.OAuth2FailureHandler;
import kakaotech.kangwon3.beforeselling.global.security.oauth2.handler.OAuth2SuccessHandler;
import kakaotech.kangwon3.beforeselling.global.security.oauth2.repository.NoOpOAuth2AuthorizedClientRepository;
import kakaotech.kangwon3.beforeselling.global.security.oauth2.repository.RedisOAuth2AuthorizationRequestRepository;
import kakaotech.kangwon3.beforeselling.global.util.ApiResponseWriter;
import lombok.RequiredArgsConstructor;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.security.config.annotation.method.configuration.EnableMethodSecurity;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.annotation.web.configurers.AbstractHttpConfigurer;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.authentication.UsernamePasswordAuthenticationFilter;
import org.springframework.security.web.servlet.util.matcher.PathPatternRequestMatcher;
import org.springframework.security.web.util.matcher.OrRequestMatcher;
import org.springframework.security.web.util.matcher.RequestMatcher;
import org.springframework.web.cors.CorsConfiguration;
import org.springframework.web.cors.CorsConfigurationSource;
import org.springframework.web.cors.UrlBasedCorsConfigurationSource;

import java.util.Arrays;
import java.util.List;

@Configuration
@EnableWebSecurity
@EnableMethodSecurity
@RequiredArgsConstructor
public class SecurityConfig {

    /** 인증 없이 접근 가능한 경로.  */
    private static final String[] PUBLIC_ENDPOINTS = {
            "/oauth2/**",
            "/login/oauth2/**",
            "/api/v1/auth/reissue",
            "/error",
    };

    private final AppProperties appProperties;
    private final JwtProvider jwtProvider;
    private final ApiResponseWriter apiResponseWriter;
    private final CustomOAuth2UserService customOAuth2UserService;
    private final OAuth2SuccessHandler oAuth2SuccessHandler;
    private final OAuth2FailureHandler oAuth2FailureHandler;
    private final RedisOAuth2AuthorizationRequestRepository authorizationRequestRepository;

    @Bean
    public SecurityFilterChain securityFilterChain(HttpSecurity http) throws Exception {
        JwtAuthenticationFilter jwtAuthenticationFilter = new JwtAuthenticationFilter(jwtProvider, publicEndpointMatcher());
        JwtExceptionFilter jwtExceptionFilter = new JwtExceptionFilter(apiResponseWriter);

        http
                .cors(cors -> cors.configurationSource(corsConfigurationSource()))
                .csrf(AbstractHttpConfigurer::disable)
                .formLogin(AbstractHttpConfigurer::disable)
                .httpBasic(AbstractHttpConfigurer::disable)
                .logout(AbstractHttpConfigurer::disable)
                .requestCache(AbstractHttpConfigurer::disable)
                .sessionManagement(session -> session.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
                .authorizeHttpRequests(authorize -> authorize
                        .requestMatchers(PUBLIC_ENDPOINTS).permitAll()
                        .anyRequest().authenticated())
                .oauth2Login(oauth2 -> oauth2
                        .authorizationEndpoint(endpoint -> endpoint
                                .authorizationRequestRepository(authorizationRequestRepository))
                        .userInfoEndpoint(endpoint -> endpoint.userService(customOAuth2UserService))
                        .authorizedClientRepository(new NoOpOAuth2AuthorizedClientRepository())
                        .successHandler(oAuth2SuccessHandler)
                        .failureHandler(oAuth2FailureHandler))
                .addFilterBefore(jwtAuthenticationFilter, UsernamePasswordAuthenticationFilter.class)
                .addFilterBefore(jwtExceptionFilter, JwtAuthenticationFilter.class)
                .exceptionHandling(exception -> exception
                        .authenticationEntryPoint(new CustomAuthenticationEntryPoint(apiResponseWriter))
                        .accessDeniedHandler(new CustomAccessDeniedHandler(apiResponseWriter)));

        return http.build();
    }

    @Bean
    public CorsConfigurationSource corsConfigurationSource() {
        CorsConfiguration configuration = new CorsConfiguration();
        configuration.setAllowedOrigins(appProperties.cors().allowedOrigins());
        configuration.setAllowedMethods(List.of(
                HttpMethod.GET.name(), HttpMethod.POST.name(), HttpMethod.PUT.name(),
                HttpMethod.PATCH.name(), HttpMethod.DELETE.name(), HttpMethod.OPTIONS.name()));
        configuration.setAllowedHeaders(List.of(HttpHeaders.AUTHORIZATION, HttpHeaders.CONTENT_TYPE));
        // 리프레시 토큰 쿠키를 주고받기 위해 credentials 허용 (allowedOrigins에 와일드카드 사용 불가)
        configuration.setAllowCredentials(true);

        UrlBasedCorsConfigurationSource source = new UrlBasedCorsConfigurationSource();
        source.registerCorsConfiguration("/**", configuration);
        return source;
    }

    private RequestMatcher publicEndpointMatcher() {
        return new OrRequestMatcher(Arrays.stream(PUBLIC_ENDPOINTS)
                .map(PathPatternRequestMatcher::pathPattern)
                .map(RequestMatcher.class::cast)
                .toList());
    }
}
