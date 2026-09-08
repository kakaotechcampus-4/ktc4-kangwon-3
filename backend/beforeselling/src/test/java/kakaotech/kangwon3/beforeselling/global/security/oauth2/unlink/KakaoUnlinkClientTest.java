package kakaotech.kangwon3.beforeselling.global.security.oauth2.unlink;

import kakaotech.kangwon3.beforeselling.domains.user.domain.entity.SocialProvider;
import kakaotech.kangwon3.beforeselling.domains.user.domain.entity.User;
import kakaotech.kangwon3.beforeselling.global.config.properties.SocialUnlinkProperties;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpMethod;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestClient;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.content;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.header;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.method;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.requestTo;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withSuccess;

class KakaoUnlinkClientTest {

    @Test
    @DisplayName("Admin Key와 socialId로 카카오 unlink API를 호출한다.")
    void unlink_thenCallKakaoUnlinkApiWithAdminKeyAndSocialId() {
        // given
        RestClient.Builder builder = RestClient.builder();
        MockRestServiceServer server = MockRestServiceServer.bindTo(builder).build();
        RestClient restClient = builder.build();

        SocialUnlinkProperties properties = new SocialUnlinkProperties(new SocialUnlinkProperties.Kakao("admin-key-value"));
        KakaoUnlinkClient client = new KakaoUnlinkClient(restClient, properties);
        User user = User.socialSignup(SocialProvider.KAKAO, "kakao-social-id", "user@example.com", "사용자");

        server.expect(requestTo("https://kapi.kakao.com/v1/user/unlink"))
                .andExpect(method(HttpMethod.POST))
                .andExpect(header("Authorization", "KakaoAK admin-key-value"))
                .andExpect(content().string("target_id_type=user_id&target_id=kakao-social-id"))
                .andRespond(withSuccess());

        // when
        client.unlink(user);

        // then
        server.verify();
    }

    @Test
    @DisplayName("KAKAO provider를 반환한다.")
    void provider_thenReturnKakao() {
        RestClient restClient = RestClient.builder().build();
        KakaoUnlinkClient client = new KakaoUnlinkClient(restClient,
                new SocialUnlinkProperties(new SocialUnlinkProperties.Kakao("admin-key-value")));

        assertThat(client.provider()).isEqualTo(SocialProvider.KAKAO);
    }
}
