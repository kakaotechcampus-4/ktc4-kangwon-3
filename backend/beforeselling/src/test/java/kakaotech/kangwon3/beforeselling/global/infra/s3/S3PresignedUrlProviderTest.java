package kakaotech.kangwon3.beforeselling.global.infra.s3;

import kakaotech.kangwon3.beforeselling.global.config.properties.S3Properties;
import kakaotech.kangwon3.beforeselling.global.exception.BaseException;
import kakaotech.kangwon3.beforeselling.global.infra.s3.dto.PresignedUrlRequest.FileMeta;
import kakaotech.kangwon3.beforeselling.global.infra.s3.dto.PresignedUrlResponse;
import kakaotech.kangwon3.beforeselling.global.infra.s3.domain.service.S3FileService;
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
import java.text.Normalizer;
import java.time.Duration;
import java.util.List;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.then;

@ExtendWith(MockitoExtension.class)
class S3PresignedUrlProviderTest {

    private static final UUID USER_ID = UUID.randomUUID();

    @Mock
    private S3Presigner s3Presigner;

    @Mock
    private PresignedPutObjectRequest presignedPutObjectRequest;

    @Mock
    private S3FileService s3FileService;

    private S3PresignedUrlProvider s3PresignedUrlProvider;

    @BeforeEach
    void setUp() {
        S3Properties s3Properties = new S3Properties(
                "test-bucket", "ap-northeast-2",
                Duration.ofMinutes(5), DataSize.ofMegabytes(10), List.of("jpg", "jpeg", "png", "webp", "heic", "heif"), null);
        s3PresignedUrlProvider = new S3PresignedUrlProvider(s3Presigner, s3Properties, s3FileService);
    }

    @Test
    @DisplayName("정상적인 파일 정보로 요청하면 S3 key 규칙에 맞는 key와 presignedUrl을 발급한다.")
    void issuePresignedUrls_withValidFile_thenReturnPresignedFile() throws Exception {
        // given
        URL presignedUrl = URI.create("https://test-bucket.s3.ap-northeast-2.amazonaws.com/signed").toURL();
        given(presignedPutObjectRequest.url()).willReturn(presignedUrl);
        given(s3Presigner.presignPutObject(any(PutObjectPresignRequest.class))).willReturn(presignedPutObjectRequest);

        FileMeta file = new FileMeta(FileType.PRODUCT_MAIN, "thumb.jpg", 1024L);

        // when
        PresignedUrlResponse response = s3PresignedUrlProvider.issuePresignedUrls(USER_ID, List.of(file));

        // then
        assertThat(response.files()).hasSize(1);
        PresignedUrlResponse.PresignedFile presignedFile = response.files().get(0);
        assertThat(presignedFile.fileName()).isEqualTo("thumb.jpg");
        assertThat(presignedFile.key()).matches("product-main/" + USER_ID + "/[0-9a-f-]+_thumb\\.jpg");
        assertThat(presignedFile.presignedUrl()).isEqualTo(presignedUrl.toString());
        assertThat(presignedFile.contentType()).isEqualTo("image/jpeg");
    }

    @Test
    @DisplayName("presigned URL을 발급하면 발급된 key가 PENDING 상태로 기록된다.")
    void issuePresignedUrls_thenMarkKeyAsPending() throws Exception {
        // given
        URL presignedUrl = URI.create("https://test-bucket.s3.ap-northeast-2.amazonaws.com/signed").toURL();
        given(presignedPutObjectRequest.url()).willReturn(presignedUrl);
        given(s3Presigner.presignPutObject(any(PutObjectPresignRequest.class))).willReturn(presignedPutObjectRequest);

        FileMeta file = new FileMeta(FileType.PRODUCT_MAIN, "thumb.jpg", 1024L);

        // when
        PresignedUrlResponse response = s3PresignedUrlProvider.issuePresignedUrls(USER_ID, List.of(file));

        // then
        String issuedKey = response.files().get(0).key();
        then(s3FileService).should().markPending(issuedKey);
    }

    @Test
    @DisplayName("자소분리(NFD)된 파일명을 NFC로 정규화하여 처리한다.")
    void issuePresignedUrls_withNfdFileName_thenNormalizeToNfc() throws Exception {
        // given
        URL presignedUrl = URI.create("https://test-bucket.s3.ap-northeast-2.amazonaws.com/signed").toURL();
        given(presignedPutObjectRequest.url()).willReturn(presignedUrl);
        given(s3Presigner.presignPutObject(any(PutObjectPresignRequest.class))).willReturn(presignedPutObjectRequest);

        String nfcFileName = Normalizer.normalize("사진.jpg", Normalizer.Form.NFC);
        String nfdFileName = Normalizer.normalize("사진.jpg", Normalizer.Form.NFD);
        FileMeta file = new FileMeta(FileType.PRODUCT_MAIN, nfdFileName, 1024L);

        // when
        PresignedUrlResponse response = s3PresignedUrlProvider.issuePresignedUrls(USER_ID, List.of(file));

        // then
        PresignedUrlResponse.PresignedFile presignedFile = response.files().get(0);
        assertThat(presignedFile.fileName()).isEqualTo(nfcFileName);
        assertThat(presignedFile.key()).contains(nfcFileName);
        assertThat(presignedFile.key()).doesNotContain(nfdFileName);
    }

    @Test
    @DisplayName("HEIC/HEIF처럼 Spring MediaTypeFactory에 없는 확장자도 fallback 매핑으로 Content-Type을 찾아 발급한다.")
    void issuePresignedUrls_withHeicFile_thenResolveFallbackContentType() throws Exception {
        // given
        URL presignedUrl = URI.create("https://test-bucket.s3.ap-northeast-2.amazonaws.com/signed").toURL();
        given(presignedPutObjectRequest.url()).willReturn(presignedUrl);
        given(s3Presigner.presignPutObject(any(PutObjectPresignRequest.class))).willReturn(presignedPutObjectRequest);

        FileMeta file = new FileMeta(FileType.PRODUCT_MAIN, "photo.heic", 1024L);

        // when
        PresignedUrlResponse response = s3PresignedUrlProvider.issuePresignedUrls(USER_ID, List.of(file));

        // then
        assertThat(response.files().get(0).contentType()).isEqualTo("image/heic");
    }

    @Test
    @DisplayName("허용되지 않은 확장자로 요청하면 FILE-001 예외가 발생한다.")
    void issuePresignedUrls_withUnsupportedExtension_thenThrowException() {
        FileMeta file = new FileMeta(FileType.PRODUCT_MAIN, "malware.exe", 1024L);

        assertThatThrownBy(() -> s3PresignedUrlProvider.issuePresignedUrls(USER_ID, List.of(file)))
                .isInstanceOf(BaseException.class)
                .extracting(e -> ((BaseException) e).getResponseCode())
                .isEqualTo(FileResponseCode.NOT_SUPPORTED_EXTENSION);
    }

    @Test
    @DisplayName("허용 확장자 목록에는 있지만 Content-Type을 알 수 없는 확장자는 설정 오류로 간주해 IllegalStateException이 발생한다.")
    void issuePresignedUrls_withAllowedExtensionButUnresolvableContentType_thenThrowException() {
        // given
        S3Properties misconfiguredProperties = new S3Properties(
                "test-bucket", "ap-northeast-2",
                Duration.ofMinutes(5), DataSize.ofMegabytes(10), List.of("unknown"), null);
        S3PresignedUrlProvider provider = new S3PresignedUrlProvider(s3Presigner, misconfiguredProperties, s3FileService);

        FileMeta file = new FileMeta(FileType.PRODUCT_MAIN, "thumb.unknown", 1024L);

        // when & then
        assertThatThrownBy(() -> provider.issuePresignedUrls(USER_ID, List.of(file)))
                .isInstanceOf(IllegalStateException.class);
    }

    @Test
    @DisplayName("허용 확장자 설정이 대문자여도 소문자 확장자 파일을 정상적으로 허용한다.")
    void issuePresignedUrls_withUpperCaseAllowedExtension_thenAllow() throws Exception {
        // given
        S3Properties upperCaseExtensionProperties = new S3Properties(
                "test-bucket", "ap-northeast-2",
                Duration.ofMinutes(5), DataSize.ofMegabytes(10), List.of("JPG", "JPEG", "PNG", "WEBP"), null);
        S3PresignedUrlProvider provider = new S3PresignedUrlProvider(s3Presigner, upperCaseExtensionProperties, s3FileService);

        URL presignedUrl = URI.create("https://test-bucket.s3.ap-northeast-2.amazonaws.com/signed").toURL();
        given(presignedPutObjectRequest.url()).willReturn(presignedUrl);
        given(s3Presigner.presignPutObject(any(PutObjectPresignRequest.class))).willReturn(presignedPutObjectRequest);

        FileMeta file = new FileMeta(FileType.PRODUCT_MAIN, "thumb.jpg", 1024L);

        // when
        PresignedUrlResponse response = provider.issuePresignedUrls(USER_ID, List.of(file));

        // then
        assertThat(response.files()).hasSize(1);
    }

    @Test
    @DisplayName("허용 크기를 초과한 파일로 요청하면 FILE-003 예외가 발생한다.")
    void issuePresignedUrls_withExceedFileSize_thenThrowException() {
        long exceedSize = DataSize.ofMegabytes(10).toBytes() + 1;
        FileMeta file = new FileMeta(FileType.PRODUCT_MAIN, "thumb.jpg", exceedSize);

        assertThatThrownBy(() -> s3PresignedUrlProvider.issuePresignedUrls(USER_ID, List.of(file)))
                .isInstanceOf(BaseException.class)
                .extracting(e -> ((BaseException) e).getResponseCode())
                .isEqualTo(FileResponseCode.EXCEED_FILE_SIZE);
    }
}
