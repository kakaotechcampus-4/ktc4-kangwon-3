package kakaotech.kangwon3.beforeselling.domains.auth.domain.service;

import kakaotech.kangwon3.beforeselling.domains.auth.domain.repository.RefreshTokenRepository;
import kakaotech.kangwon3.beforeselling.global.exception.BaseException;
import kakaotech.kangwon3.beforeselling.global.security.constant.AuthResponseCode;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.time.Duration;

@Service
@RequiredArgsConstructor
public class RefreshTokenService {

    private final RefreshTokenRepository refreshTokenRepository;

    public void saveRefreshToken(String jti, Long userId, Duration ttl) {
        refreshTokenRepository.insertRefreshToken(jti, userId, ttl);
    }

    /**
     * 리프레시 토큰을 소비합니다.
     * 조회와 삭제를 Redis GETDEL로 원자적으로 처리하여, 동일한 리프레시 토큰으로 동시에 재발급을 요청해도 둘 중 하나만 성공합니다.
     */
    public void consumeRefreshToken(String jti, Long userId) {
        Long storedUserId = refreshTokenRepository.getAndDeleteUserIdByJti(jti)
                .orElseThrow(() -> new BaseException(AuthResponseCode.INVALID_REFRESH_TOKEN));

        if (!storedUserId.equals(userId)) {
            throw new BaseException(AuthResponseCode.INVALID_REFRESH_TOKEN);
        }
    }

    public void removeRefreshToken(String jti) {
        refreshTokenRepository.deleteRefreshToken(jti);
    }
}
