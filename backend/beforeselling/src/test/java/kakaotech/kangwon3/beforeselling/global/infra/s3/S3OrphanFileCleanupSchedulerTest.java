package kakaotech.kangwon3.beforeselling.global.infra.s3;

import kakaotech.kangwon3.beforeselling.global.infra.s3.domain.entity.S3File;
import kakaotech.kangwon3.beforeselling.global.infra.s3.domain.service.S3FileService;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Captor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.data.domain.Pageable;

import java.time.LocalDateTime;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.then;
import static org.mockito.BDDMockito.willThrow;

@ExtendWith(MockitoExtension.class)
class S3OrphanFileCleanupSchedulerTest {

    @Mock
    private S3FileService s3FileService;

    @Mock
    private S3ObjectDeleter s3ObjectDeleter;

    @InjectMocks
    private S3OrphanFileCleanupScheduler scheduler;

    @Captor
    private ArgumentCaptor<LocalDateTime> thresholdCaptor;

    @Test
    @DisplayName("만료된 PENDING 파일이 여러 배치에 걸쳐 있으면 더 이상 없을 때까지 반복해서 삭제한다.")
    void cleanupOrphanFiles_withMultipleBatches_thenDeleteUntilEmpty() {
        // given
        S3File first = S3File.pending("a.jpg");
        S3File second = S3File.pending("b.jpg");
        given(s3FileService.findExpiredPending(any(), any(Pageable.class)))
                .willReturn(List.of(first, second))
                .willReturn(List.of());

        // when
        scheduler.cleanupOrphanFiles();

        // then
        then(s3ObjectDeleter).should().deleteAll(List.of("a.jpg", "b.jpg"));
        then(s3FileService).should().removeByKeys(List.of("a.jpg", "b.jpg"));
        then(s3FileService).should(org.mockito.BDDMockito.times(2))
                .findExpiredPending(thresholdCaptor.capture(), any(Pageable.class));
        assertThat(thresholdCaptor.getValue()).isBeforeOrEqualTo(LocalDateTime.now().minusHours(24));
    }

    @Test
    @DisplayName("만료된 PENDING 파일이 없으면 삭제를 시도하지 않는다.")
    void cleanupOrphanFiles_withNoExpiredFiles_thenDoNothing() {
        // given
        given(s3FileService.findExpiredPending(any(), any(Pageable.class))).willReturn(List.of());

        // when
        scheduler.cleanupOrphanFiles();

        // then
        then(s3ObjectDeleter).should(org.mockito.BDDMockito.never()).deleteAll(any());
        then(s3FileService).should(org.mockito.BDDMockito.never()).removeByKeys(any());
    }

    @Test
    @DisplayName("S3 삭제가 실패하면 부기 레코드를 지우지 않고 다음 배치 조회도 중단한다.")
    void cleanupOrphanFiles_withDeleteFailure_thenStopWithoutRemovingBookkeeping() {
        // given
        S3File file = S3File.pending("a.jpg");
        given(s3FileService.findExpiredPending(any(), any(Pageable.class))).willReturn(List.of(file));
        willThrow(new RuntimeException("S3 장애")).given(s3ObjectDeleter).deleteAll(List.of("a.jpg"));

        // when
        scheduler.cleanupOrphanFiles();

        // then
        then(s3FileService).should(org.mockito.BDDMockito.never()).removeByKeys(any());
        then(s3FileService).should(org.mockito.BDDMockito.times(1))
                .findExpiredPending(any(), any(Pageable.class));
    }
}
