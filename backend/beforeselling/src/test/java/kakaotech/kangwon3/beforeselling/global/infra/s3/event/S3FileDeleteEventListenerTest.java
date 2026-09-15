package kakaotech.kangwon3.beforeselling.global.infra.s3.event;

import kakaotech.kangwon3.beforeselling.global.infra.s3.S3FileDeleter;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.List;

import static org.mockito.BDDMockito.then;

@ExtendWith(MockitoExtension.class)
class S3FileDeleteEventListenerTest {

    @Mock
    private S3FileDeleter s3FileDeleter;

    @InjectMocks
    private S3FileDeleteEventListener s3FileDeleteEventListener;

    @Test
    @DisplayName("S3FileDeleteEvent를 수신하면 이벤트에 담긴 key 목록으로 S3FileDeleter에 삭제를 위임한다.")
    void handle_withEvent_thenDelegateToS3FileDeleter() {
        // given
        List<String> keys = List.of("product-main/1/a.jpg");
        S3FileDeleteEvent event = new S3FileDeleteEvent(keys);

        // when
        s3FileDeleteEventListener.handle(event);

        // then
        then(s3FileDeleter).should().deleteAll(keys);
    }
}
