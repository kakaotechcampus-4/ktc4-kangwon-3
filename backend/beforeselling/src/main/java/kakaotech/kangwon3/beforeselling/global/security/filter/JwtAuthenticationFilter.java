package kakaotech.kangwon3.beforeselling.global.security.filter;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import kakaotech.kangwon3.beforeselling.global.security.jwt.JwtProvider;
import kakaotech.kangwon3.beforeselling.global.security.jwt.TokenClaims;
import kakaotech.kangwon3.beforeselling.global.security.jwt.TokenType;
import kakaotech.kangwon3.beforeselling.global.security.principal.UserPrincipal;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpHeaders;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.web.util.matcher.RequestMatcher;
import org.springframework.util.StringUtils;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.util.List;

/**
 * Authorization: Bearer {accessToken} 헤더를 검증해 SecurityContext에 인증 정보를 채웁니다.
 * 토큰 클레임만으로 UserPrincipal을 구성하므로 요청마다 DB를 조회하지 않습니다.
 * 토큰 검증 실패는 BaseException으로 던져지며, 앞단의 JwtExceptionFilter가 공통 응답으로 변환합니다.
 */
@RequiredArgsConstructor
public class JwtAuthenticationFilter extends OncePerRequestFilter {

    private static final String BEARER_PREFIX = "Bearer ";

    private final JwtProvider jwtProvider;
    private final RequestMatcher skipMatcher;

    @Override
    protected boolean shouldNotFilter(HttpServletRequest request) {
        // 공개 엔드포인트(재발급 등)에서는 만료된 액세스 토큰이 실려 와도 요청을 막지 않는다
        return skipMatcher.matches(request);
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response,
                                    FilterChain filterChain) throws ServletException, IOException {
        String accessToken = resolveAccessToken(request);

        if (accessToken != null) {
            TokenClaims claims = jwtProvider.parse(accessToken, TokenType.ACCESS);
            SecurityContextHolder.getContext().setAuthentication(toAuthentication(claims));
        }

        filterChain.doFilter(request, response);
    }

    private String resolveAccessToken(HttpServletRequest request) {
        String header = request.getHeader(HttpHeaders.AUTHORIZATION);
        if (StringUtils.hasText(header) && header.startsWith(BEARER_PREFIX)) {
            return header.substring(BEARER_PREFIX.length());
        }
        return null;
    }

    private Authentication toAuthentication(TokenClaims claims) {
        UserPrincipal principal = new UserPrincipal(claims.userId(), claims.role());
        return UsernamePasswordAuthenticationToken.authenticated(
                principal, null, List.of(new SimpleGrantedAuthority(claims.role().getAuthority())));
    }
}
