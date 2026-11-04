package kakaotech.kangwon3.beforeselling.global.security.oauth2.repository;

import kakaotech.kangwon3.beforeselling.support.RedisContainerSupport;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.autoconfigure.ImportAutoConfiguration;
import org.springframework.boot.data.redis.test.autoconfigure.DataRedisTest;
import org.springframework.boot.jackson.autoconfigure.JacksonAutoConfiguration;
import org.springframework.context.annotation.Import;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;
import org.springframework.security.oauth2.core.endpoint.OAuth2AuthorizationRequest;
import org.springframework.security.oauth2.core.endpoint.OAuth2ParameterNames;
import org.springframework.test.context.ActiveProfiles;

import java.util.Map;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;

@Tag("integration")
@DataRedisTest
@ActiveProfiles("test")
@ImportAutoConfiguration(JacksonAutoConfiguration.class)
@Import(RedisOAuth2AuthorizationRequestRepository.class)
class RedisOAuth2AuthorizationRequestRepositoryTest extends RedisContainerSupport {

    private static final String STATE = "test-state";
    private static final String KEY = RedisOAuth2AuthorizationRequestRepository.KEY_PREFIX + STATE;

    @Autowired
    private RedisOAuth2AuthorizationRequestRepository repository;

    @Autowired
    private StringRedisTemplate redisTemplate;

    private final MockHttpServletResponse response = new MockHttpServletResponse();

    @AfterEach
    void tearDown() {
        redisTemplate.delete(KEY);
    }

    @Test
    @DisplayName("인가 요청을 저장하면 state로 같은 내용의 인가 요청을 다시 읽을 수 있다.")
    void saveAndLoad_thenRestoreSameAuthorizationRequest() {
        // given
        OAuth2AuthorizationRequest authorizationRequest = authorizationRequest();
        repository.saveAuthorizationRequest(authorizationRequest, new MockHttpServletRequest(), response);

        // when
        OAuth2AuthorizationRequest loaded = repository.loadAuthorizationRequest(requestWithState(STATE));

        // then
        assertThat(loaded).isNotNull();
        assertThat(loaded.getAuthorizationUri()).isEqualTo(authorizationRequest.getAuthorizationUri());
        assertThat(loaded.getClientId()).isEqualTo(authorizationRequest.getClientId());
        assertThat(loaded.getRedirectUri()).isEqualTo(authorizationRequest.getRedirectUri());
        assertThat(loaded.getScopes()).isEqualTo(authorizationRequest.getScopes());
        assertThat(loaded.getState()).isEqualTo(STATE);
        assertThat(loaded.getAdditionalParameters()).isEqualTo(authorizationRequest.getAdditionalParameters());
        assertThat(loaded.getAttributes()).isEqualTo(authorizationRequest.getAttributes());
        assertThat(loaded.getAuthorizationRequestUri()).isEqualTo(authorizationRequest.getAuthorizationRequestUri());
    }

    @Test
    @DisplayName("인가 요청은 3분 뒤 만료되도록 저장된다.")
    void saveAuthorizationRequest_thenExpireIn3Minutes() {
        // when
        repository.saveAuthorizationRequest(authorizationRequest(), new MockHttpServletRequest(), response);

        // then
        assertThat(redisTemplate.getExpire(KEY))
                .isPositive()
                .isLessThanOrEqualTo(RedisOAuth2AuthorizationRequestRepository.TTL.toSeconds());
    }

    @Test
    @DisplayName("state가 없거나 저장되지 않은 state면 인가 요청을 찾지 못한다.")
    void loadAuthorizationRequest_withoutStoredState_thenNull() {
        // when & then
        assertThat(repository.loadAuthorizationRequest(new MockHttpServletRequest())).isNull();
        assertThat(repository.loadAuthorizationRequest(requestWithState("unknown-state"))).isNull();
    }

    @Test
    @DisplayName("인가 요청을 꺼내 삭제하면 다시 읽을 수 없다.")
    void removeAuthorizationRequest_thenReturnAndDelete() {
        // given
        repository.saveAuthorizationRequest(authorizationRequest(), new MockHttpServletRequest(), response);

        // when
        OAuth2AuthorizationRequest removed = repository.removeAuthorizationRequest(requestWithState(STATE), response);

        // then
        assertThat(removed).isNotNull();
        assertThat(removed.getState()).isEqualTo(STATE);
        assertThat(repository.loadAuthorizationRequest(requestWithState(STATE))).isNull();
    }

    @Test
    @DisplayName("null을 저장하면 기존 인가 요청을 삭제한다.")
    void saveAuthorizationRequest_withNull_thenRemoveExisting() {
        // given
        repository.saveAuthorizationRequest(authorizationRequest(), new MockHttpServletRequest(), response);

        // when
        repository.saveAuthorizationRequest(null, requestWithState(STATE), response);

        // then
        assertThat(redisTemplate.hasKey(KEY)).isFalse();
    }

    private OAuth2AuthorizationRequest authorizationRequest() {
        return OAuth2AuthorizationRequest.authorizationCode()
                .authorizationUri("https://kauth.kakao.com/oauth/authorize")
                .clientId("test-kakao-client-id")
                .redirectUri("http://localhost:8080/login/oauth2/code/kakao")
                .scopes(Set.of("profile_nickname", "account_email"))
                .state(STATE)
                .additionalParameters(Map.of("prompt", "login"))
                .attributes(Map.of(OAuth2ParameterNames.REGISTRATION_ID, "kakao"))
                .authorizationRequestUri("https://kauth.kakao.com/oauth/authorize?response_type=code&state=" + STATE)
                .build();
    }

    private MockHttpServletRequest requestWithState(String state) {
        MockHttpServletRequest request = new MockHttpServletRequest();
        request.setParameter(OAuth2ParameterNames.STATE, state);
        return request;
    }
}
