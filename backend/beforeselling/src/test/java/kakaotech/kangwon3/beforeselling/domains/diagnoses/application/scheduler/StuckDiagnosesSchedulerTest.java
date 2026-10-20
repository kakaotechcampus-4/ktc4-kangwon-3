package kakaotech.kangwon3.beforeselling.domains.diagnoses.application.scheduler;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.service.ProductService;
import kakaotech.kangwon3.beforeselling.global.config.properties.DiagnosesProperties;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.dao.PessimisticLockingFailureException;

import java.time.Duration;
import java.time.LocalDateTime;
import java.util.List;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatCode;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.never;
import static org.mockito.BDDMockito.then;

@ExtendWith(MockitoExtension.class)
class StuckDiagnosesSchedulerTest {

    private static final Duration STUCK_THRESHOLD = Duration.ofMinutes(15);

    @Mock
    private ProductService productService;

    private StuckDiagnosesScheduler scheduler;

    @BeforeEach
    void setUp() {
        scheduler = new StuckDiagnosesScheduler(productService,
                new DiagnosesProperties(STUCK_THRESHOLD, Duration.ofSeconds(3), Duration.ofMinutes(10)));
    }

    @Test
    @DisplayName("현재 시각에서 기준 시간을 뺀 시각으로 한 묶음을 조회하고, 같은 기준 시각으로 상품마다 실패 처리한다.")
    void failStuckDiagnoses_thenUseSameThresholdForQueryAndEachProduct() {
        // given
        UUID first = UUID.randomUUID();
        UUID second = UUID.randomUUID();
        given(productService.findStuckProductIds(any(), eq(StuckDiagnosesScheduler.BATCH_SIZE)))
                .willReturn(List.of(first, second));
        given(productService.failStuckDiagnoses(any(), any())).willReturn(true);
        LocalDateTime before = LocalDateTime.now();

        // when
        scheduler.failStuckDiagnoses();

        // then
        LocalDateTime after = LocalDateTime.now();
        ArgumentCaptor<LocalDateTime> threshold = ArgumentCaptor.forClass(LocalDateTime.class);
        then(productService).should().findStuckProductIds(threshold.capture(), eq(StuckDiagnosesScheduler.BATCH_SIZE));
        assertThat(threshold.getValue())
                .isBetween(before.minus(STUCK_THRESHOLD), after.minus(STUCK_THRESHOLD));
        then(productService).should().failStuckDiagnoses(first, threshold.getValue());
        then(productService).should().failStuckDiagnoses(second, threshold.getValue());
    }

    @Test
    @DisplayName("한 상품 처리 중 락 대기 초과나 예상하지 못한 예외가 나도 나머지 상품은 처리한다.")
    void failStuckDiagnoses_whenOneProductThrows_thenContinueWithOthers() {
        // given
        UUID lockTimeout = UUID.randomUUID();
        UUID unexpected = UUID.randomUUID();
        UUID remaining = UUID.randomUUID();
        given(productService.findStuckProductIds(any(), eq(StuckDiagnosesScheduler.BATCH_SIZE)))
                .willReturn(List.of(lockTimeout, unexpected, remaining));
        given(productService.failStuckDiagnoses(eq(lockTimeout), any()))
                .willThrow(new PessimisticLockingFailureException("lock timeout"));
        given(productService.failStuckDiagnoses(eq(unexpected), any()))
                .willThrow(new IllegalStateException("boom"));
        given(productService.failStuckDiagnoses(eq(remaining), any())).willReturn(true);

        // when & then
        assertThatCode(scheduler::failStuckDiagnoses).doesNotThrowAnyException();
        then(productService).should().failStuckDiagnoses(eq(remaining), any());
    }

    @Test
    @DisplayName("멈춘 진단이 없으면 실패 처리를 요청하지 않는다.")
    void failStuckDiagnoses_whenNothingStuck_thenDoNothing() {
        // given
        given(productService.findStuckProductIds(any(), eq(StuckDiagnosesScheduler.BATCH_SIZE)))
                .willReturn(List.of());

        // when
        scheduler.failStuckDiagnoses();

        // then
        then(productService).should(never()).failStuckDiagnoses(any(), any());
    }
}
