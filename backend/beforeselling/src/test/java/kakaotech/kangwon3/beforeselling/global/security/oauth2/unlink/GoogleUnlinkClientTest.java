package kakaotech.kangwon3.beforeselling.global.security.oauth2.unlink;

import kakaotech.kangwon3.beforeselling.domains.user.domain.entity.SocialProvider;
import kakaotech.kangwon3.beforeselling.domains.user.domain.entity.User;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpMethod;
import org.springframework.test.util.ReflectionTestUtils;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestClient;

import static org.springframework.test.web.client.match.MockRestRequestMatchers.content;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.method;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.requestTo;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withSuccess;

class GoogleUnlinkClientTest {

    @Test
    @DisplayName("저장된 refresh_token으로 구글 revoke API를 호출한다.")
    void unlink_withRefreshToken_thenCallGoogleRevokeApi() {
        // given
        RestClient.Builder builder = RestClient.builder();
        MockRestServiceServer server = MockRestServiceServer.bindTo(builder).build();
        RestClient restClient = builder.build();

        GoogleUnlinkClient client = new GoogleUnlinkClient(restClient);
        User user = userWithRefreshToken("google-refresh-token");

        server.expect(requestTo("https://oauth2.googleapis.com/revoke"))
                .andExpect(method(HttpMethod.POST))
                .andExpect(content().string("token=google-refresh-token"))
                .andRespond(withSuccess());

        // when
        client.unlink(user);

        // then
        server.verify();
    }

    @Test
    @DisplayName("refresh_token이 없으면 API를 호출하지 않고 건너뛴다.")
    void unlink_withoutRefreshToken_thenSkip() {
        // given
        RestClient.Builder builder = RestClient.builder();
        MockRestServiceServer server = MockRestServiceServer.bindTo(builder).build();
        RestClient restClient = builder.build();

        GoogleUnlinkClient client = new GoogleUnlinkClient(restClient);
        User user = User.socialSignup(SocialProvider.GOOGLE, "google-social-id", "user@example.com", "사용자");

        // when
        client.unlink(user);

        // then: 아무 요청도 기대(expect)해두지 않았으므로, 실제로 호출이 있었다면
        // MockRestServiceServer가 즉시 AssertionError를 던진다.
        server.verify();
    }

    private User userWithRefreshToken(String refreshToken) {
        User user = User.socialSignup(SocialProvider.GOOGLE, "google-social-id", "user@example.com", "사용자");
        ReflectionTestUtils.setField(user, "socialRefreshToken", refreshToken);
        return user;
    }
}
