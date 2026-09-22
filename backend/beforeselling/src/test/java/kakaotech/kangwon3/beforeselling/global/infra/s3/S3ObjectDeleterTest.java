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
import software.amazon.awssdk.services.s3.S3Client;
import software.amazon.awssdk.services.s3.model.DeleteObjectsRequest;
import software.amazon.awssdk.services.s3.model.DeleteObjectsResponse;
import software.amazon.awssdk.services.s3.model.ObjectIdentifier;

import java.time.Duration;
import java.util.List;
import java.util.stream.IntStream;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.then;

@ExtendWith(MockitoExtension.class)
class S3ObjectDeleterTest {

    @Mock
    private S3Client s3Client;

    @Captor
    private ArgumentCaptor<DeleteObjectsRequest> requestCaptor;

    private S3ObjectDeleter s3ObjectDeleter;

    @BeforeEach
    void setUp() {
        S3Properties s3Properties = new S3Properties(
                "test-bucket", "ap-northeast-2",
                Duration.ofMinutes(5), DataSize.ofMegabytes(10), List.of("jpg"), null);
        s3ObjectDeleter = new S3ObjectDeleter(s3Client, s3Properties);
    }

    @Test
    @DisplayName("key 목록을 전달하면 버킷을 지정해 DeleteObjects 요청을 한 번 보낸다.")
    void deleteAll_withFewKeys_thenSendSingleRequest() {
        // given
        given(s3Client.deleteObjects(any(DeleteObjectsRequest.class)))
                .willReturn(DeleteObjectsResponse.builder().build());

        // when
        s3ObjectDeleter.deleteAll(List.of("a.jpg", "b.jpg"));

        // then
        then(s3Client).should().deleteObjects(requestCaptor.capture());
        DeleteObjectsRequest request = requestCaptor.getValue();
        assertThat(request.bucket()).isEqualTo("test-bucket");
        assertThat(request.delete().objects())
                .extracting(ObjectIdentifier::key)
                .containsExactly("a.jpg", "b.jpg");
    }

    @Test
    @DisplayName("1000개를 초과하는 key는 S3 DeleteObjects 1회 최대 제한에 맞춰 여러 번의 요청으로 나뉘어 전송된다.")
    void deleteAll_withMoreThanThousandKeys_thenSendChunkedRequests() {
        // given
        given(s3Client.deleteObjects(any(DeleteObjectsRequest.class)))
                .willReturn(DeleteObjectsResponse.builder().build());
        List<String> keys = IntStream.range(0, 1500)
                .mapToObj(i -> "key-" + i)
                .toList();

        // when
        s3ObjectDeleter.deleteAll(keys);

        // then
        then(s3Client).should(org.mockito.BDDMockito.times(2)).deleteObjects(requestCaptor.capture());
        List<DeleteObjectsRequest> requests = requestCaptor.getAllValues();
        assertThat(requests.get(0).delete().objects()).hasSize(1000);
        assertThat(requests.get(1).delete().objects()).hasSize(500);
    }

    @Test
    @DisplayName("빈 key 목록이면 삭제 요청을 보내지 않는다.")
    void deleteAll_withEmptyKeys_thenSkip() {
        // when
        s3ObjectDeleter.deleteAll(List.of());

        // then
        then(s3Client).should(org.mockito.BDDMockito.never()).deleteObjects(any(DeleteObjectsRequest.class));
    }
}
