package kakaotech.kangwon3.beforeselling.domains.diagnoses.application.scheduler;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.usecase.AiDiagnosesRequestUseCase;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.event.AiDiagnosesRequestedEvent;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.service.DiagnosesService;
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
import java.util.Optional;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatCode;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.never;
import static org.mockito.BDDMockito.then;

@ExtendWith(MockitoExtension.class)
class PendingDiagnosesRetrySchedulerTest {

    private static final Duration REQUEST_RETRY_DEADLINE = Duration.ofMinutes(10);

    @Mock
    private ProductService productService;

    @Mock
    private DiagnosesService diagnosesService;

    @Mock
    private AiDiagnosesRequestUseCase aiDiagnosesRequestUseCase;

    private PendingDiagnosesRetryScheduler scheduler;

    @BeforeEach
    void setUp() {
        scheduler = new PendingDiagnosesRetryScheduler(productService, diagnosesService, aiDiagnosesRequestUseCase,
                new DiagnosesProperties(Duration.ofMinutes(15), Duration.ofSeconds(3), REQUEST_RETRY_DEADLINE));
    }

    @Test
    @DisplayName("대기 상품이 있는 진단서마다 현재 시각에서 재요청 기한을 뺀 시각으로 재시작하고, 보낼 상품이 있으면 AI에 다시 요청한다.")
    void retryPendingDiagnoses_thenRestartWithDeadlineAndRequest() {
        // given
        UUID first = UUID.randomUUID();
        UUID second = UUID.randomUUID();
        AiDiagnosesRequestedEvent event = new AiDiagnosesRequestedEvent(first, List.of());
        given(productService.findPendingDiagnosesIds(PendingDiagnosesRetryScheduler.BATCH_SIZE))
                .willReturn(List.of(first, second));
        given(diagnosesService.restartPendingProducts(eq(first), any())).willReturn(Optional.of(event));
        given(diagnosesService.restartPendingProducts(eq(second), any())).willReturn(Optional.empty());
        LocalDateTime before = LocalDateTime.now();

        // when
        scheduler.retryPendingDiagnoses();

        // then
        LocalDateTime after = LocalDateTime.now();
        ArgumentCaptor<LocalDateTime> deadline = ArgumentCaptor.forClass(LocalDateTime.class);
        then(diagnosesService).should().restartPendingProducts(eq(first), deadline.capture());
        assertThat(deadline.getValue())
                .isBetween(before.minus(REQUEST_RETRY_DEADLINE), after.minus(REQUEST_RETRY_DEADLINE));
        then(diagnosesService).should().restartPendingProducts(second, deadline.getValue());
        then(aiDiagnosesRequestUseCase).should().requestDiagnoses(event);
        then(aiDiagnosesRequestUseCase).shouldHaveNoMoreInteractions();
    }

    @Test
    @DisplayName("한 진단서 처리 중 락 대기 초과나 예상하지 못한 예외가 나도 나머지 진단서는 재요청한다.")
    void retryPendingDiagnoses_whenOneDiagnosesThrows_thenContinueWithOthers() {
        // given
        UUID lockTimeout = UUID.randomUUID();
        UUID unexpected = UUID.randomUUID();
        UUID remaining = UUID.randomUUID();
        AiDiagnosesRequestedEvent event = new AiDiagnosesRequestedEvent(remaining, List.of());
        given(productService.findPendingDiagnosesIds(PendingDiagnosesRetryScheduler.BATCH_SIZE))
                .willReturn(List.of(lockTimeout, unexpected, remaining));
        given(diagnosesService.restartPendingProducts(eq(lockTimeout), any()))
                .willThrow(new PessimisticLockingFailureException("lock timeout"));
        given(diagnosesService.restartPendingProducts(eq(unexpected), any()))
                .willThrow(new IllegalStateException("boom"));
        given(diagnosesService.restartPendingProducts(eq(remaining), any())).willReturn(Optional.of(event));

        // when & then
        assertThatCode(scheduler::retryPendingDiagnoses).doesNotThrowAnyException();
        then(aiDiagnosesRequestUseCase).should().requestDiagnoses(event);
    }

    @Test
    @DisplayName("대기 상품이 없으면 재요청하지 않는다.")
    void retryPendingDiagnoses_whenNothingPending_thenDoNothing() {
        // given
        given(productService.findPendingDiagnosesIds(PendingDiagnosesRetryScheduler.BATCH_SIZE)).willReturn(List.of());

        // when
        scheduler.retryPendingDiagnoses();

        // then
        then(diagnosesService).should(never()).restartPendingProducts(any(), any());
        then(aiDiagnosesRequestUseCase).should(never()).requestDiagnoses(any());
    }
}
