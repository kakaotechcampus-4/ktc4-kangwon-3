package kakaotech.kangwon3.beforeselling.global.infra.s3;

import kakaotech.kangwon3.beforeselling.global.config.properties.S3Properties;
import kakaotech.kangwon3.beforeselling.global.exception.BaseException;
import kakaotech.kangwon3.beforeselling.global.infra.s3.dto.PresignedUrlRequest.FileMeta;
import kakaotech.kangwon3.beforeselling.global.infra.s3.dto.PresignedUrlResponse;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.util.unit.DataSize;
import software.amazon.awssdk.services.s3.presigner.S3Presigner;
import software.amazon.awssdk.services.s3.presigner.model.PresignedPutObjectRequest;
import software.amazon.awssdk.services.s3.presigner.model.PutObjectPresignRequest;

import java.net.URI;
import java.net.URL;
import java.time.Duration;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.BDDMockito.given;

@ExtendWith(MockitoExtension.class)
class S3PresignedUrlProviderTest {

    @Mock
    private S3Presigner s3Presigner;

    @Mock
    private PresignedPutObjectRequest presignedPutObjectRequest;

    private S3PresignedUrlProvider s3PresignedUrlProvider;

    @BeforeEach
    void setUp() {
        S3Properties s3Properties = new S3Properties(
                "test-bucket", "ap-northeast-2",
                Duration.ofMinutes(5), DataSize.ofMegabytes(10), List.of("jpg", "jpeg", "png", "webp"));
        s3PresignedUrlProvider = new S3PresignedUrlProvider(s3Presigner, s3Properties);
    }

    @Test
    @DisplayName("정상적인 파일 정보로 요청하면 S3 key 규칙에 맞는 presignedUrl과 fileUrl을 발급한다.")
    void issuePresignedUrls_withValidFile_thenReturnPresignedFile() throws Exception {
        // given
        URL presignedUrl = URI.create("https://test-bucket.s3.ap-northeast-2.amazonaws.com/signed").toURL();
        given(presignedPutObjectRequest.url()).willReturn(presignedUrl);
        given(s3Presigner.presignPutObject(any(PutObjectPresignRequest.class))).willReturn(presignedPutObjectRequest);

        FileMeta file = new FileMeta(FileType.PRODUCT_MAIN, "thumb.jpg", "image/jpeg", 1024L);

        // when
        PresignedUrlResponse response = s3PresignedUrlProvider.issuePresignedUrls(1L, List.of(file));

        // then
        assertThat(response.files()).hasSize(1);
        PresignedUrlResponse.PresignedFile presignedFile = response.files().get(0);
        assertThat(presignedFile.fileName()).isEqualTo("thumb.jpg");
        assertThat(presignedFile.presignedUrl()).isEqualTo(presignedUrl.toString());
        assertThat(presignedFile.fileUrl())
                .matches("https://test-bucket\\.s3\\.ap-northeast-2\\.amazonaws\\.com/product-main/1/[0-9a-f-]+_thumb\\.jpg");
    }

    @Test
    @DisplayName("허용되지 않은 확장자로 요청하면 FILE-001 예외가 발생한다.")
    void issuePresignedUrls_withUnsupportedExtension_thenThrowException() {
        FileMeta file = new FileMeta(FileType.PRODUCT_MAIN, "malware.exe", "application/octet-stream", 1024L);

        assertThatThrownBy(() -> s3PresignedUrlProvider.issuePresignedUrls(1L, List.of(file)))
                .isInstanceOf(BaseException.class)
                .extracting(e -> ((BaseException) e).getResponseCode())
                .isEqualTo(FileResponseCode.NOT_SUPPORTED_EXTENSION);
    }

    @Test
    @DisplayName("허용 크기를 초과한 파일로 요청하면 FILE-003 예외가 발생한다.")
    void issuePresignedUrls_withExceedFileSize_thenThrowException() {
        long exceedSize = DataSize.ofMegabytes(10).toBytes() + 1;
        FileMeta file = new FileMeta(FileType.PRODUCT_MAIN, "thumb.jpg", "image/jpeg", exceedSize);

        assertThatThrownBy(() -> s3PresignedUrlProvider.issuePresignedUrls(1L, List.of(file)))
                .isInstanceOf(BaseException.class)
                .extracting(e -> ((BaseException) e).getResponseCode())
                .isEqualTo(FileResponseCode.EXCEED_FILE_SIZE);
    }
}
