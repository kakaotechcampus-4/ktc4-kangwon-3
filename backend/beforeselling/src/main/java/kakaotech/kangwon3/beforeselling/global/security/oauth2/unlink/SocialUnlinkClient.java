package kakaotech.kangwon3.beforeselling.global.security.oauth2.unlink;

import kakaotech.kangwon3.beforeselling.domains.user.domain.entity.SocialProvider;
import kakaotech.kangwon3.beforeselling.domains.user.domain.entity.User;

/**
 * 소셜 제공자 연동 해제(unlink) 클라이언트. provider별로 하나씩 구현체를 둔다.
 */
public interface SocialUnlinkClient {

    SocialProvider provider();

    void unlink(User user);
}
