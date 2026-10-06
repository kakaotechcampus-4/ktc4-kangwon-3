package kakaotech.kangwon3.beforeselling.global.security.jwt;

import kakaotech.kangwon3.beforeselling.domains.user.domain.entity.Role;

import java.util.UUID;

public record TokenClaims(
        UUID userId,
        Role role,
        TokenType type,
        String jti
) {
}
