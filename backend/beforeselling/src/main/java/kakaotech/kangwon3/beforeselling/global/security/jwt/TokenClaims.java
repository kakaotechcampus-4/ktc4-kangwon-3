package kakaotech.kangwon3.beforeselling.global.security.jwt;

import kakaotech.kangwon3.beforeselling.domains.user.domain.entity.Role;

public record TokenClaims(
        Long userId,
        Role role,
        TokenType type,
        String jti
) {
}
