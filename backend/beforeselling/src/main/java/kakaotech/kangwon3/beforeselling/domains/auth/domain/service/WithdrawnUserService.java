package kakaotech.kangwon3.beforeselling.domains.auth.domain.service;

import kakaotech.kangwon3.beforeselling.domains.auth.domain.repository.WithdrawnUserRepository;
import kakaotech.kangwon3.beforeselling.global.security.jwt.JwtProvider;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.dao.DataAccessException;
import org.springframework.stereotype.Service;

import java.util.UUID;

/**
 * 탈퇴 후에도 만료 전인 액세스 토큰을 막기 위한 블랙리스트.
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class WithdrawnUserService {

    private final WithdrawnUserRepository withdrawnUserRepository;
    private final JwtProvider jwtProvider;

    public void saveWithdrawnUser(UUID userId) {
        withdrawnUserRepository.insertWithdrawnUser(userId, jwtProvider.getAccessTokenExpiration());
    }

    /**
     * Redis 조회에 실패하면 인증 전체가 막히지 않도록 탈퇴하지 않은 것으로 봅니다(fail-open).
     */
    public boolean isWithdrawn(UUID userId) {
        try {
            return withdrawnUserRepository.existsByUserId(userId);
        } catch (DataAccessException e) {
            log.warn("탈퇴 회원 블랙리스트 조회에 실패해 요청을 통과시킵니다. userId={}", userId, e);
            return false;
        }
    }
}
