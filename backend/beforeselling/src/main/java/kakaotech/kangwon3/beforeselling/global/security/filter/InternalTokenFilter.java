package kakaotech.kangwon3.beforeselling.global.security.filter;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.extern.slf4j.Slf4j;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.List;

/**
 * AI 서버가 호출하는 내부 API(/internal/**)를 X-Internal-Token 헤더로 인증합니다.
 * 토큰이 없거나 다르면 인증 정보를 채우지 않고 넘기며, 인가 단계에서 401로 응답됩니다.
 */
@Slf4j
public class InternalTokenFilter extends OncePerRequestFilter {

    public static final String HEADER_NAME = "X-Internal-Token";

    private static final String PRINCIPAL = "ai-server";
    private static final List<GrantedAuthority> AUTHORITIES = List.of(new SimpleGrantedAuthority("ROLE_INTERNAL"));

    private final byte[] expectedToken;

    public InternalTokenFilter(String token) {
        this.expectedToken = token.getBytes(StandardCharsets.UTF_8);
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response,
                                    FilterChain filterChain) throws ServletException, IOException {
        String token = request.getHeader(HEADER_NAME);

        // 일치하는 앞부분 길이에 따라 비교 시간이 달라지지 않도록 상수 시간 비교를 쓴다.
        if (token != null && MessageDigest.isEqual(token.getBytes(StandardCharsets.UTF_8), expectedToken)) {
            SecurityContextHolder.getContext().setAuthentication(
                    UsernamePasswordAuthenticationToken.authenticated(PRINCIPAL, null, AUTHORITIES));
        } else {
            // 토큰 값은 남기지 않는다.
            log.warn("내부 API 인증 실패: uri={}, remoteAddr={}, tokenPresent={}",
                    request.getRequestURI(), request.getRemoteAddr(), token != null);
        }

        filterChain.doFilter(request, response);
    }
}
