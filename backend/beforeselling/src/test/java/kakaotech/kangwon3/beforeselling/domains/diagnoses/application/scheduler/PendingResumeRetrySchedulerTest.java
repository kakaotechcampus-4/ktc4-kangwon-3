package kakaotech.kangwon3.beforeselling.domains.diagnoses.application.scheduler;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.usecase.AiResumeRequestUseCase;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.event.AiResumeRequestedEvent;
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
import static org.mockito.ArgumentMatchers.anyBoolean;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.never;
import static org.mockito.BDDMockito.then;

@ExtendWith(MockitoExtension.class)
class PendingResumeRetrySchedulerTest {

    private static final Duration REQUEST_RETRY_DEADLINE = Duration.ofMinutes(10);

    @Mock
    private ProductService productService;

    @Mock
    private AiResumeRequestUseCase aiResumeRequestUseCase;

    private PendingResumeRetryScheduler scheduler;

    @BeforeEach
    void setUp() {
        scheduler = new PendingResumeRetryScheduler(productService, aiResumeRequestUseCase,
                new DiagnosesProperties(Duration.ofMinutes(15), Duration.ofSeconds(3), REQUEST_RETRY_DEADLINE));
    }

    @Test
    @DisplayName("재요청을 기다리는 상품마다 현재 시각에서 재요청 기한을 뺀 시각으로 확인하고, 보낼 것이 있으면 재전송으로 다시 요청한다.")
    void retryPendingResumes_thenRestartWithDeadlineAndResend() {
        // given
        UUID first = UUID.randomUUID();
        UUID second = UUID.randomUUID();
        AiResumeRequestedEvent event = resumeEvent(first);
        given(productService.findResumePendingProductIds(PendingResumeRetryScheduler.BATCH_SIZE))
                .willReturn(List.of(first, second));
        given(productService.restartPendingResume(eq(first), any())).willReturn(Optional.of(event));
        given(productService.restartPendingResume(eq(second), any())).willReturn(Optional.empty());
        LocalDateTime before = LocalDateTime.now();

        // when
        scheduler.retryPendingResumes();

        // then
        LocalDateTime after = LocalDateTime.now();
        ArgumentCaptor<LocalDateTime> deadline = ArgumentCaptor.forClass(LocalDateTime.class);
        then(productService).should().restartPendingResume(eq(first), deadline.capture());
        assertThat(deadline.getValue())
                .isBetween(before.minus(REQUEST_RETRY_DEADLINE), after.minus(REQUEST_RETRY_DEADLINE));
        then(productService).should().restartPendingResume(second, deadline.getValue());
        then(aiResumeRequestUseCase).should().requestResume(event, true);
        then(aiResumeRequestUseCase).shouldHaveNoMoreInteractions();
    }

    @Test
    @DisplayName("한 상품 처리 중 락 대기 초과나 예상하지 못한 예외가 나도 나머지 상품은 다시 요청한다.")
    void retryPendingResumes_whenOneProductThrows_thenContinueWithOthers() {
        // given
        UUID lockTimeout = UUID.randomUUID();
        UUID unexpected = UUID.randomUUID();
        UUID remaining = UUID.randomUUID();
        AiResumeRequestedEvent event = resumeEvent(remaining);
        given(productService.findResumePendingProductIds(PendingResumeRetryScheduler.BATCH_SIZE))
                .willReturn(List.of(lockTimeout, unexpected, remaining));
        given(productService.restartPendingResume(eq(lockTimeout), any()))
                .willThrow(new PessimisticLockingFailureException("lock timeout"));
        given(productService.restartPendingResume(eq(unexpected), any()))
                .willThrow(new IllegalStateException("boom"));
        given(productService.restartPendingResume(eq(remaining), any())).willReturn(Optional.of(event));

        // when & then
        assertThatCode(scheduler::retryPendingResumes).doesNotThrowAnyException();
        then(aiResumeRequestUseCase).should().requestResume(event, true);
    }

    @Test
    @DisplayName("재요청을 기다리는 상품이 없으면 아무것도 하지 않는다.")
    void retryPendingResumes_whenNothingPending_thenDoNothing() {
        // given
        given(productService.findResumePendingProductIds(PendingResumeRetryScheduler.BATCH_SIZE)).willReturn(List.of());

        // when
        scheduler.retryPendingResumes();

        // then
        then(productService).should(never()).restartPendingResume(any(), any());
        then(aiResumeRequestUseCase).should(never()).requestResume(any(), anyBoolean());
    }

    private AiResumeRequestedEvent resumeEvent(UUID productId) {
        return new AiResumeRequestedEvent(UUID.randomUUID(), productId, "run-1", 1,
                List.of(new AiResumeRequestedEvent.Answer("sales_type", "구매대행")));
    }
}
