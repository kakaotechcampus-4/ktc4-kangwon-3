package kakaotech.kangwon3.beforeselling.global.security.oauth2;

import kakaotech.kangwon3.beforeselling.domains.user.domain.entity.User;
import kakaotech.kangwon3.beforeselling.domains.user.domain.service.UserService;
import kakaotech.kangwon3.beforeselling.global.exception.BaseException;
import kakaotech.kangwon3.beforeselling.global.security.constant.AuthResponseCode;
import kakaotech.kangwon3.beforeselling.global.security.oauth2.attribute.OAuth2Attributes;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.security.oauth2.client.userinfo.DefaultOAuth2UserService;
import org.springframework.security.oauth2.client.userinfo.OAuth2UserRequest;
import org.springframework.security.oauth2.core.OAuth2AuthenticationException;
import org.springframework.security.oauth2.core.OAuth2Error;
import org.springframework.security.oauth2.core.user.OAuth2User;
import org.springframework.stereotype.Service;

/**
 * 제공자 사용자 정보 조회 후, 서비스 회원을 조회하거나 자동 가입 (로그인 == 회원가입)
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class CustomOAuth2UserService extends DefaultOAuth2UserService {

    private final UserService userService;

    @Override
    public OAuth2User loadUser(OAuth2UserRequest userRequest) throws OAuth2AuthenticationException {
        OAuth2User oAuth2User = super.loadUser(userRequest);
        String registrationId = userRequest.getClientRegistration().getRegistrationId();

        try {
            OAuth2Attributes attributes = OAuth2Attributes.of(registrationId, oAuth2User.getAttributes());
            if (attributes.getSocialId() == null) {
                log.error("소셜 사용자 식별자를 찾을 수 없습니다. registrationId={}", registrationId);
                throw new BaseException(AuthResponseCode.OAUTH2_LOGIN_FAILED);
            }

            User user = userService.getOrCreateUser(
                    attributes.getProvider(), attributes.getSocialId(), attributes.getEmail(), attributes.getName());

            return new CustomOAuth2User(user.getId(), user.getRole(), oAuth2User.getAttributes());
        } catch (BaseException e) {
            // 필터 체인(OAuth2LoginAuthenticationFilter) 내부이므로 @RestControllerAdvice가 아닌 실패 핸들러가 처리하도록 변환
            OAuth2Error error = new OAuth2Error(e.getResponseCode().getCode(), e.getMessage(), null);
            throw new OAuth2AuthenticationException(error, e);
        }
    }
}
