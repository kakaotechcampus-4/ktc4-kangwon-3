package kakaotech.kangwon3.beforeselling.global.security.oauth2.unlink;

import kakaotech.kangwon3.beforeselling.domains.user.domain.entity.SocialProvider;
import kakaotech.kangwon3.beforeselling.domains.user.domain.entity.User;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

import java.util.List;
import java.util.Map;
import java.util.function.Function;
import java.util.stream.Collectors;

@Slf4j
@Component
public class SocialUnlinkService {

    private final Map<SocialProvider, SocialUnlinkClient> clientsByProvider;

    public SocialUnlinkService(List<SocialUnlinkClient> clients) {
        this.clientsByProvider = clients.stream()
                .collect(Collectors.toMap(SocialUnlinkClient::provider, Function.identity()));
    }

    public void unlink(User user) {
        SocialUnlinkClient client = clientsByProvider.get(user.getSocialProvider());
        if (client == null) {
            log.warn("등록되지 않은 provider의 unlink 요청입니다. provider={}", user.getSocialProvider());
            return;
        }
        try {
            client.unlink(user);
        } catch (Exception e) {
            log.error("소셜 unlink 실패. userId={}, provider={}, socialId={}",
                    user.getId(), user.getSocialProvider(), user.getSocialId(), e);
        }
    }
}
