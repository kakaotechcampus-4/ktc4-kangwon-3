package kakaotech.kangwon3.beforeselling.domains.user.domain.service;

import kakaotech.kangwon3.beforeselling.domains.user.domain.entity.User;

/**
 * 소셜 로그인 조회/가입 결과
 */
public record UserLookupResult(
        User user,
        boolean isNewUser
) {
}
