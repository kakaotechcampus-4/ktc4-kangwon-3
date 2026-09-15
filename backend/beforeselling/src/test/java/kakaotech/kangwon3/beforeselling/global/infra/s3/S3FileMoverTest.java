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
import software.amazon.awssdk.awscore.exception.AwsServiceException;
import software.amazon.awssdk.services.s3.S3Client;
import software.amazon.awssdk.services.s3.model.CopyObjectRequest;
import software.amazon.awssdk.services.s3.model.CopyObjectResponse;
import software.amazon.awssdk.services.s3.model.DeleteObjectRequest;
import software.amazon.awssdk.services.s3.model.DeleteObjectResponse;
import software.amazon.awssdk.services.s3.model.NoSuchKeyException;

import java.time.Duration;
import java.util.Arrays;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.never;
import static org.mockito.BDDMockito.then;
import static org.mockito.BDDMockito.times;
import static org.mockito.BDDMockito.willThrow;

@ExtendWith(MockitoExtension.class)
class S3FileMoverTest {

    @Mock
    private S3Client s3Client;

    @Captor
    private ArgumentCaptor<CopyObjectRequest> copyRequestCaptor;

    @Captor
    private ArgumentCaptor<DeleteObjectRequest> deleteRequestCaptor;

    private S3FileMover s3FileMover;

    @BeforeEach
    void setUp() {
        S3Properties s3Properties = new S3Properties(
                "test-bucket", "ap-northeast-2",
                Duration.ofMinutes(5), DataSize.ofMegabytes(10), List.of("jpg"));
        s3FileMover = new S3FileMover(s3Client, s3Properties);
    }

    @Test
    @DisplayName("temp 경로 key를 이동시키면 정식 경로로 copy한 뒤 temp 원본을 삭제하고 정식 key를 반환한다.")
    void moveToPermanent_withTempKey_thenCopyAndDeleteThenReturnPermanentKey() {
        // given
        given(s3Client.copyObject(any(CopyObjectRequest.class))).willReturn(CopyObjectResponse.builder().build());
        given(s3Client.deleteObject(any(DeleteObjectRequest.class))).willReturn(DeleteObjectResponse.builder().build());

        String tempKey = "temp/product-main/1/uuid_thumb.jpg";

        // when
        String permanentKey = s3FileMover.moveToPermanent(tempKey);

        // then
        assertThat(permanentKey).isEqualTo("product-main/1/uuid_thumb.jpg");

        then(s3Client).should().copyObject(copyRequestCaptor.capture());
        CopyObjectRequest copyRequest = copyRequestCaptor.getValue();
        assertThat(copyRequest.sourceBucket()).isEqualTo("test-bucket");
        assertThat(copyRequest.sourceKey()).isEqualTo("temp/product-main/1/uuid_thumb.jpg");
        assertThat(copyRequest.destinationBucket()).isEqualTo("test-bucket");
        assertThat(copyRequest.destinationKey()).isEqualTo("product-main/1/uuid_thumb.jpg");

        then(s3Client).should().deleteObject(deleteRequestCaptor.capture());
        assertThat(deleteRequestCaptor.getValue().key()).isEqualTo("temp/product-main/1/uuid_thumb.jpg");
    }

    @Test
    @DisplayName("temp 경로가 아닌 key는 이동을 건너뛰고 그대로 반환한다.")
    void moveToPermanent_withNonTempKey_thenNoOpAndReturnAsIs() {
        // given
        String permanentKey = "product-main/1/uuid_thumb.jpg";

        // when
        String result = s3FileMover.moveToPermanent(permanentKey);

        // then
        assertThat(result).isEqualTo(permanentKey);
        then(s3Client).should(never()).copyObject(any(CopyObjectRequest.class));
        then(s3Client).should(never()).deleteObject(any(DeleteObjectRequest.class));
    }

    @Test
    @DisplayName("null이나 빈 key는 이동을 건너뛰고 그대로 반환한다.")
    void moveToPermanent_withBlankKey_thenReturnAsIs() {
        assertThat(s3FileMover.moveToPermanent(null)).isNull();
        assertThat(s3FileMover.moveToPermanent("")).isEmpty();
        then(s3Client).should(never()).copyObject(any(CopyObjectRequest.class));
    }

    @Test
    @DisplayName("temp 원본이 존재하지 않아 copy가 실패하면 원본 예외를 그대로 전파한다.")
    void moveToPermanent_withMissingTempObject_thenPropagateOriginalException() {
        // given
        willThrow(NoSuchKeyException.builder().message("no such key").build())
                .given(s3Client).copyObject(any(CopyObjectRequest.class));

        String tempKey = "temp/product-main/1/uuid_thumb.jpg";

        // when & then
        assertThatThrownBy(() -> s3FileMover.moveToPermanent(tempKey))
                .isInstanceOf(NoSuchKeyException.class);

        then(s3Client).should(never()).deleteObject(any(DeleteObjectRequest.class));
    }

    @Test
    @DisplayName("여러 장 이동 중 일부만 실패하면 이미 이동된 파일은 그대로 두고 예외만 전파한다.")
    void moveAllToPermanent_withPartialFailure_thenPropagateExceptionWithoutRollback() {
        // given
        given(s3Client.copyObject(any(CopyObjectRequest.class)))
                .willReturn(CopyObjectResponse.builder().build())
                .willThrow(AwsServiceException.builder().message("boom").build());
        given(s3Client.deleteObject(any(DeleteObjectRequest.class))).willReturn(DeleteObjectResponse.builder().build());

        List<String> tempKeys = Arrays.asList(
                "temp/product-detail/1/a.jpg",
                "temp/product-detail/1/b.jpg"
        );

        // when & then
        assertThatThrownBy(() -> s3FileMover.moveAllToPermanent(tempKeys))
                .isInstanceOf(AwsServiceException.class);

        then(s3Client).should(times(2)).copyObject(any(CopyObjectRequest.class));
        then(s3Client).should(times(1)).deleteObject(any(DeleteObjectRequest.class));
    }

    @Test
    @DisplayName("key 목록이 null이면 null을 그대로 반환한다.")
    void moveAllToPermanent_withNullList_thenReturnNull() {
        assertThat(s3FileMover.moveAllToPermanent(null)).isNull();
    }
}
