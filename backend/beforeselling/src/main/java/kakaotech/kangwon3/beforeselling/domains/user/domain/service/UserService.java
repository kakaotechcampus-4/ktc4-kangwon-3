package kakaotech.kangwon3.beforeselling.domains.user.domain.service;

import kakaotech.kangwon3.beforeselling.domains.user.domain.entity.SocialProvider;
import kakaotech.kangwon3.beforeselling.domains.user.domain.entity.User;
import kakaotech.kangwon3.beforeselling.domains.user.domain.repository.UserRepository;
import kakaotech.kangwon3.beforeselling.global.common.CommonResponseCode;
import kakaotech.kangwon3.beforeselling.global.exception.BaseException;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Slf4j
@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class UserService {

    private final UserRepository userRepository;

    public User getUser(Long userId) {
        return userRepository.findById(userId)
                .orElseThrow(() -> new BaseException(CommonResponseCode.NOT_FOUND));
    }

    /**
     * 소셜 로그인 사용자를 조회하고, 없으면 자동 가입 (로그인 == 회원가입)
     */
    @Transactional
    public User getOrCreateUser(SocialProvider socialProvider, String socialId,
                                String email, String name) {
        return userRepository.findBySocialProviderAndSocialId(socialProvider, socialId)
                .orElseGet(() -> createUser(socialProvider, socialId, email, name));
    }

    private User createUser(SocialProvider socialProvider, String socialId,
                            String email, String name) {
        try {
            return userRepository.saveAndFlush(User.socialSignup(socialProvider, socialId, email, name));
        } catch (DataIntegrityViolationException e) {
            log.warn("소셜 사용자 동시 가입 감지, 재조회합니다. provider={}, socialId={}", socialProvider, socialId);
            return userRepository.findBySocialProviderAndSocialId(socialProvider, socialId)
                    .orElseThrow(() -> e);
        }
    }

    @Transactional
    public void withdraw(Long userId) {
        User user = getUser(userId);
        userRepository.delete(user);
        log.debug("회원 탈퇴 처리 완료. userId={}", userId);
    }
}
