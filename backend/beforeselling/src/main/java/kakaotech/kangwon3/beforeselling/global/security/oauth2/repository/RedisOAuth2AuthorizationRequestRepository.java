package kakaotech.kangwon3.beforeselling.global.security.oauth2.repository;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.security.oauth2.client.web.AuthorizationRequestRepository;
import org.springframework.security.oauth2.core.endpoint.OAuth2AuthorizationRequest;
import org.springframework.security.oauth2.core.endpoint.OAuth2ParameterNames;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;
import tools.jackson.databind.json.JsonMapper;

import java.time.Duration;

/**
 * 세션을 사용하지 않는(STATELESS) 환경에서 OAuth2 인가 요청을 Redis에 보관합니다.
 * 인가 서버가 콜백 시 그대로 돌려주는 state 파라미터를 키로 사용합니다.
 */
@Component
@RequiredArgsConstructor
public class RedisOAuth2AuthorizationRequestRepository
        implements AuthorizationRequestRepository<OAuth2AuthorizationRequest> {

    static final String KEY_PREFIX = "oauth2:auth_request:";
    static final Duration TTL = Duration.ofMinutes(3);

    private final StringRedisTemplate redisTemplate;
    private final JsonMapper jsonMapper;

    @Override
    public OAuth2AuthorizationRequest loadAuthorizationRequest(HttpServletRequest request) {
        String state = request.getParameter(OAuth2ParameterNames.STATE);
        if (!StringUtils.hasText(state)) {
            return null;
        }

        String json = redisTemplate.opsForValue().get(keyOf(state));
        if (json == null) {
            return null;
        }
        return jsonMapper.readValue(json, OAuth2AuthorizationRequestSnapshot.class).toAuthorizationRequest();
    }

    @Override
    public void saveAuthorizationRequest(OAuth2AuthorizationRequest authorizationRequest,
                                         HttpServletRequest request,
                                         HttpServletResponse response) {
        if (authorizationRequest == null) {
            removeAuthorizationRequest(request, response);
            return;
        }

        String json = jsonMapper.writeValueAsString(OAuth2AuthorizationRequestSnapshot.from(authorizationRequest));
        redisTemplate.opsForValue().set(keyOf(authorizationRequest.getState()), json, TTL);
    }

    @Override
    public OAuth2AuthorizationRequest removeAuthorizationRequest(HttpServletRequest request,
                                                                 HttpServletResponse response) {
        OAuth2AuthorizationRequest authorizationRequest = loadAuthorizationRequest(request);
        if (authorizationRequest != null) {
            redisTemplate.delete(keyOf(authorizationRequest.getState()));
        }
        return authorizationRequest;
    }

    private String keyOf(String state) {
        return KEY_PREFIX + state;
    }
}
