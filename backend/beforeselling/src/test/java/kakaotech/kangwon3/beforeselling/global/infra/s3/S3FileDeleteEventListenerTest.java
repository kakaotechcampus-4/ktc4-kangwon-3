package kakaotech.kangwon3.beforeselling.global.infra.s3;

import kakaotech.kangwon3.beforeselling.global.infra.s3.domain.service.S3FileService;
import kakaotech.kangwon3.beforeselling.global.infra.s3.event.S3FileDeleteRequestedEvent;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThatCode;
import static org.mockito.BDDMockito.then;
import static org.mockito.BDDMockito.willThrow;

@ExtendWith(MockitoExtension.class)
class S3FileDeleteEventListenerTest {

    private static final List<String> KEYS = List.of("diagnoses/1/uuid_a.jpg", "diagnoses/1/uuid_b.jpg");

    @Mock
    private S3ObjectDeleter s3ObjectDeleter;

    @Mock
    private S3FileService s3FileService;

    @InjectMocks
    private S3FileDeleteEventListener s3FileDeleteEventListener;

    @Test
    @DisplayName("삭제 이벤트를 수신하면 S3 객체를 삭제하고 부기 레코드도 함께 제거한다.")
    void handle_thenDeleteS3ObjectsAndBookkeepingRows() {
        // when
        s3FileDeleteEventListener.handle(new S3FileDeleteRequestedEvent(KEYS));

        // then
        then(s3ObjectDeleter).should().deleteAll(KEYS);
        then(s3FileService).should().removeByKeys(KEYS);
    }

    @Test
    @DisplayName("S3 삭제가 실패해도 예외를 삼키고 부기 레코드는 정리하지 않는다.")
    void handle_withS3Failure_thenSwallowExceptionAndKeepBookkeeping() {
        // given
        willThrow(new RuntimeException("S3 장애")).given(s3ObjectDeleter).deleteAll(KEYS);

        // when & then
        assertThatCode(() -> s3FileDeleteEventListener.handle(new S3FileDeleteRequestedEvent(KEYS)))
                .doesNotThrowAnyException();
        then(s3FileService).should(org.mockito.BDDMockito.never()).removeByKeys(KEYS);
    }
}
