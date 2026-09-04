package kakaotech.kangwon3.beforeselling.global.security.oauth2;

import kakaotech.kangwon3.beforeselling.domains.user.domain.entity.Role;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.oauth2.core.user.OAuth2User;

import java.util.Collection;
import java.util.List;
import java.util.Map;

/**
 * 소셜 로그인 직후 성공 핸들러에 전달되는 인증 주체.
 */
public record CustomOAuth2User(
        Long userId,
        Role role,
        Map<String, Object> attributes
) implements OAuth2User {

    @Override
    public Map<String, Object> getAttributes() {
        return attributes;
    }

    @Override
    public Collection<? extends GrantedAuthority> getAuthorities() {
        return List.of(new SimpleGrantedAuthority(role.getAuthority()));
    }

    @Override
    public String getName() {
        return String.valueOf(userId);
    }
}
