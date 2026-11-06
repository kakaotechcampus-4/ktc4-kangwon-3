package kakaotech.kangwon3.beforeselling.global.ratelimit;

import kakaotech.kangwon3.beforeselling.domains.user.domain.entity.Role;
import kakaotech.kangwon3.beforeselling.global.security.principal.UserPrincipal;
import kakaotech.kangwon3.beforeselling.global.util.ApiResponseWriter;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.http.HttpHeaders;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;
import org.springframework.security.authentication.AnonymousAuthenticationToken;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.authority.AuthorityUtils;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.web.method.HandlerMethod;
import org.springframework.web.servlet.resource.ResourceHttpRequestHandler;
import tools.jackson.databind.json.JsonMapper;

import java.util.List;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.then;
import static org.mockito.Mockito.verifyNoInteractions;

@ExtendWith(MockitoExtension.class)
class RateLimitInterceptorTest {

    private static final UUID USER_ID = UUID.randomUUID();

    private final JsonMapper jsonMapper = JsonMapper.builder().build();
    private final MockHttpServletRequest request = new MockHttpServletRequest();
    private final MockHttpServletResponse response = new MockHttpServletResponse();

    @Mock
    private RateLimiter rateLimiter;

    @AfterEach
    void clearSecurityContext() {
        SecurityContextHolder.clearContext();
    }

    @Test
    @DisplayName("로그인 사용자의 일반 API 요청은 기본 한도에서 차감하고 통과시킨다")
    void consumesDefaultPolicyForUnannotatedHandler() throws Exception {
        // given
        loginAs(USER_ID);
        given(rateLimiter.tryConsume(RateLimitPolicy.DEFAULT, USER_ID)).willReturn(RateLimitResult.allow());

        // when
        boolean proceed = interceptor().preHandle(request, response, handlerOf("normal"));

        // then
        assertThat(proceed).isTrue();
        then(rateLimiter).should().tryConsume(RateLimitPolicy.DEFAULT, USER_ID);
    }

    @Test
    @DisplayName("@RateLimit(AI)가 붙은 API 요청은 AI 한도에서 차감한다")
    void consumesAnnotatedPolicy() throws Exception {
        // given
        loginAs(USER_ID);
        given(rateLimiter.tryConsume(RateLimitPolicy.AI, USER_ID)).willReturn(RateLimitResult.allow());

        // when
        boolean proceed = interceptor().preHandle(request, response, handlerOf("ai"));

        // then
        assertThat(proceed).isTrue();
        then(rateLimiter).should().tryConsume(RateLimitPolicy.AI, USER_ID);
    }

    @Test
    @DisplayName("한도를 넘은 요청은 막고 429, COMMON-011, Retry-After 헤더로 응답한다")
    void rejectsWithTooManyRequests() throws Exception {
        // given
        loginAs(USER_ID);
        given(rateLimiter.tryConsume(RateLimitPolicy.AI, USER_ID)).willReturn(RateLimitResult.reject(30));

        // when
        boolean proceed = interceptor().preHandle(request, response, handlerOf("ai"));

        // then
        assertThat(proceed).isFalse();
        assertThat(response.getStatus()).isEqualTo(429);
        assertThat(response.getHeader(HttpHeaders.RETRY_AFTER)).isEqualTo("30");
        assertThat(jsonMapper.readTree(response.getContentAsString()).get("code").asString()).isEqualTo("COMMON-011");
    }

    @Test
    @DisplayName("한도를 확인하다 Redis 오류 등 예외가 나면 요청을 막지 않고 통과시킨다")
    void passesWhenRateLimiterFails() throws Exception {
        // given
        loginAs(USER_ID);
        given(rateLimiter.tryConsume(RateLimitPolicy.DEFAULT, USER_ID)).willThrow(new IllegalStateException("redis down"));

        // when
        boolean proceed = interceptor().preHandle(request, response, handlerOf("normal"));

        // then
        assertThat(proceed).isTrue();
        assertThat(response.getStatus()).isEqualTo(200);
    }

    @Test
    @DisplayName("로그인하지 않은 요청은 한도를 확인하지 않고 통과시킨다")
    void skipsAnonymousRequest() throws Exception {
        // given
        SecurityContextHolder.getContext().setAuthentication(new AnonymousAuthenticationToken(
                "key", "anonymousUser", AuthorityUtils.createAuthorityList("ROLE_ANONYMOUS")));

        // when
        boolean proceed = interceptor().preHandle(request, response, handlerOf("normal"));

        // then
        assertThat(proceed).isTrue();
        verifyNoInteractions(rateLimiter);
    }

    @Test
    @DisplayName("컨트롤러 메서드가 아닌 핸들러 요청은 한도를 확인하지 않고 통과시킨다")
    void skipsNonHandlerMethod() throws Exception {
        // given
        loginAs(USER_ID);

        // when
        boolean proceed = interceptor().preHandle(request, response, new ResourceHttpRequestHandler());

        // then
        assertThat(proceed).isTrue();
        verifyNoInteractions(rateLimiter);
    }

    private RateLimitInterceptor interceptor() {
        return new RateLimitInterceptor(rateLimiter, new ApiResponseWriter(jsonMapper));
    }

    private void loginAs(UUID userId) {
        UserPrincipal principal = new UserPrincipal(userId, Role.USER);
        SecurityContextHolder.getContext().setAuthentication(
                new UsernamePasswordAuthenticationToken(principal, null, List.of()));
    }

    private HandlerMethod handlerOf(String methodName) throws NoSuchMethodException {
        return new HandlerMethod(new TestController(), TestController.class.getMethod(methodName));
    }

    static class TestController {

        public void normal() {
        }

        @RateLimit(RateLimitPolicy.AI)
        public void ai() {
        }
    }
}
