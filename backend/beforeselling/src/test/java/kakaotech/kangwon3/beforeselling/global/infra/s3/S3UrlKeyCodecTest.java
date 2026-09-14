package kakaotech.kangwon3.beforeselling.global.infra.s3;

import kakaotech.kangwon3.beforeselling.global.config.properties.S3Properties;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.util.unit.DataSize;

import java.time.Duration;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class S3UrlKeyCodecTest {

    private S3UrlKeyCodec s3UrlKeyCodec;

    @BeforeEach
    void setUp() {
        S3Properties s3Properties = new S3Properties(
                "test-bucket", "ap-northeast-2",
                Duration.ofMinutes(5), DataSize.ofMegabytes(10), List.of("jpg"));
        s3UrlKeyCodec = new S3UrlKeyCodec(s3Properties);
    }

    @Test
    @DisplayName("key를 설정된 버킷/리전 기준의 fileUrl로 변환한다.")
    void toUrl_withKey_thenReturnFileUrl() {
        // given
        String key = "product-main/1/abc-uuid_thumb.jpg";

        // when
        String url = s3UrlKeyCodec.toUrl(key);

        // then
        assertThat(url).isEqualTo("https://test-bucket.s3.ap-northeast-2.amazonaws.com/product-main/1/abc-uuid_thumb.jpg");
    }

    @Test
    @DisplayName("한글/공백이 포함된 파일명은 URL-encode된 fileUrl로 변환한다.")
    void toUrl_withKoreanAndSpaceFileName_thenEncodeSegments() {
        // given
        String key = "product-detail/1/abc-uuid_사진 파일.jpg";

        // when
        String url = s3UrlKeyCodec.toUrl(key);

        // then
        assertThat(url).isEqualTo(
                "https://test-bucket.s3.ap-northeast-2.amazonaws.com/product-detail/1/abc-uuid_%EC%82%AC%EC%A7%84%20%ED%8C%8C%EC%9D%BC.jpg");
    }
}
