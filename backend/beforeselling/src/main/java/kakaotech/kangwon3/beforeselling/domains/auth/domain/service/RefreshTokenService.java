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
     * 저장된 리프레시 토큰인지, 그리고 토큰의 사용자와 저장된 사용자가 일치하는지 검증합니다.
     * 저장소에 없다면 이미 회전(재발급)되었거나 로그아웃된 토큰이므로 재사용(replay)으로 간주합니다.
     */
    public void validateRefreshToken(String jti, Long userId) {
        Long storedUserId = refreshTokenRepository.findUserIdByJti(jti)
                .orElseThrow(() -> new BaseException(AuthResponseCode.INVALID_REFRESH_TOKEN));

        if (!storedUserId.equals(userId)) {
            throw new BaseException(AuthResponseCode.INVALID_REFRESH_TOKEN);
        }
    }

    public void removeRefreshToken(String jti) {
        refreshTokenRepository.deleteRefreshToken(jti);
    }
}
