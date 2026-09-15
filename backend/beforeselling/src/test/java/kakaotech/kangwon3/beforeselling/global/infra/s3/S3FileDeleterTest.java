package kakaotech.kangwon3.beforeselling.global.infra.s3;

import kakaotech.kangwon3.beforeselling.global.config.properties.S3Properties;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Captor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.util.unit.DataSize;
import software.amazon.awssdk.core.exception.SdkException;
import software.amazon.awssdk.services.s3.S3Client;
import software.amazon.awssdk.services.s3.model.DeleteObjectsRequest;
import software.amazon.awssdk.services.s3.model.DeleteObjectsResponse;
import software.amazon.awssdk.services.s3.model.ObjectIdentifier;
import software.amazon.awssdk.services.s3.model.S3Error;

import java.time.Duration;
import java.util.Arrays;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatCode;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.never;
import static org.mockito.BDDMockito.then;
import static org.mockito.BDDMockito.times;
import static org.mockito.BDDMockito.willThrow;

@ExtendWith(MockitoExtension.class)
class S3FileDeleterTest {

    @Mock
    private S3Client s3Client;

    @Captor
    private ArgumentCaptor<DeleteObjectsRequest> requestCaptor;

    private S3FileDeleter s3FileDeleter;

    @BeforeEach
    void setUp() {
        S3Properties s3Properties = new S3Properties(
                "test-bucket", "ap-northeast-2",
                Duration.ofMinutes(5), DataSize.ofMegabytes(10), List.of("jpg"));
        s3FileDeleter = new S3FileDeleter(s3Client, s3Properties);
    }

    @Test
    @DisplayName("key 목록을 넘기면 일괄 삭제를 요청한다.")
    void deleteAll_withValidKeys_thenRequestDeleteObjects() {
        // given
        given(s3Client.deleteObjects(any(DeleteObjectsRequest.class)))
                .willReturn(DeleteObjectsResponse.builder().build());

        List<String> keys = List.of(
                "product-main/1/abc_thumb.jpg",
                "product-detail/1/def_detail.jpg"
        );

        // when
        s3FileDeleter.deleteAll(keys);

        // then
        then(s3Client).should().deleteObjects(requestCaptor.capture());
        DeleteObjectsRequest request = requestCaptor.getValue();

        assertThat(request.bucket()).isEqualTo("test-bucket");
        assertThat(request.delete().objects())
                .extracting(ObjectIdentifier::key)
                .containsExactly("product-main/1/abc_thumb.jpg", "product-detail/1/def_detail.jpg");
    }

    @Test
    @DisplayName("빈 목록이나 공백 key만 있으면 삭제 요청 자체를 보내지 않는다.")
    void deleteAll_withEmptyOrBlankKeys_thenSkipRequest() {
        // when
        s3FileDeleter.deleteAll(List.of());
        s3FileDeleter.deleteAll(Arrays.asList("", null, "   "));

        // then
        then(s3Client).should(never()).deleteObjects(any(DeleteObjectsRequest.class));
    }

    @Test
    @DisplayName("S3 응답에 일부 실패가 포함되면 최대 재시도 횟수만큼 다시 요청한 뒤 예외 없이 종료한다.")
    void deleteAll_withPersistentPartialFailure_thenRetryThenSwallow() {
        // given
        given(s3Client.deleteObjects(any(DeleteObjectsRequest.class)))
                .willReturn(DeleteObjectsResponse.builder()
                        .errors(S3Error.builder().key("broken.jpg").code("AccessDenied").build())
                        .build());

        // when & then
        assertThatCode(() -> s3FileDeleter.deleteAll(List.of("broken.jpg")))
                .doesNotThrowAnyException();

        then(s3Client).should(times(3)).deleteObjects(any(DeleteObjectsRequest.class));
    }

    @Test
    @DisplayName("첫 시도에서 실패해도 재시도 중 성공하면 더 이상 재시도하지 않는다.")
    void deleteAll_withTransientFailure_thenSucceedOnRetry() {
        // given
        given(s3Client.deleteObjects(any(DeleteObjectsRequest.class)))
                .willThrow(SdkException.create("boom", null))
                .willReturn(DeleteObjectsResponse.builder().build());

        // when
        s3FileDeleter.deleteAll(List.of("broken.jpg"));

        // then
        then(s3Client).should(times(2)).deleteObjects(any(DeleteObjectsRequest.class));
    }

    @Test
    @DisplayName("S3 호출 자체가 계속 실패해도 예외를 전파하지 않고 로그만 남긴다.")
    void deleteAll_withPersistentSdkException_thenSwallow() {
        // given
        willThrow(SdkException.create("boom", null))
                .given(s3Client).deleteObjects(any(DeleteObjectsRequest.class));

        // when & then
        assertThatCode(() -> s3FileDeleter.deleteAll(List.of("broken.jpg")))
                .doesNotThrowAnyException();

        then(s3Client).should(times(3)).deleteObjects(any(DeleteObjectsRequest.class));
    }
}
