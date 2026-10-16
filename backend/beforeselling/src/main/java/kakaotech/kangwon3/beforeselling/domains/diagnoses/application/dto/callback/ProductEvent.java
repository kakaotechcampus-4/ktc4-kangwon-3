package kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.callback;

import com.fasterxml.jackson.annotation.JsonSubTypes;
import com.fasterxml.jackson.annotation.JsonTypeInfo;

import java.util.UUID;

// AI 콜백(POST /internal/v1/ai/products/{productId}). eventType 값으로 하위 이벤트를 구분한다.
@JsonTypeInfo(use = JsonTypeInfo.Id.NAME, property = "eventType")
@JsonSubTypes({
        @JsonSubTypes.Type(value = ProductProgressEvent.class, name = "product_progress"),
        @JsonSubTypes.Type(value = ProductAwaitingInputEvent.class, name = "product_awaiting_input"),
        @JsonSubTypes.Type(value = ProductFailedEvent.class, name = "product_failed"),
        @JsonSubTypes.Type(value = ProductResultEvent.class, name = "product_result"),
})
public sealed interface ProductEvent
        permits ProductProgressEvent, ProductAwaitingInputEvent, ProductFailedEvent, ProductResultEvent {
    String eventId();

    UUID diagnosisId();

    UUID productId();

    // 실행 식별자.
    String runId();

    // 실행 안에서의 이벤트 순서
    int sequence();
}
