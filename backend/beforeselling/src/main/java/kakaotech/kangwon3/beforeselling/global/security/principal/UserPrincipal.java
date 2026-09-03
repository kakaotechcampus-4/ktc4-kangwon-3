package kakaotech.kangwon3.beforeselling.global.security.principal;

import kakaotech.kangwon3.beforeselling.domains.user.domain.entity.Role;

/**
 * JWT 클레임만으로 구성되는 인증 주체. 요청마다 DB를 조회하지 않습니다.
 * 컨트롤러에서는 {@code @AuthenticationPrincipal UserPrincipal principal}로 주입받습니다.
 */
public record UserPrincipal(
        Long userId,
        Role role
) {
}
