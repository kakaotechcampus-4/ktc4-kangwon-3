package kakaotech.kangwon3.beforeselling.domains.diagnoses.presentation.controller;

import jakarta.validation.Valid;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.callback.ProductAwaitingInputEvent;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.callback.ProductEvent;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.callback.ProductFailedEvent;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.callback.ProductProgressEvent;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.callback.ProductResultEvent;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.usecase.AiCallbackUseCase;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.presentation.api.AiCallbackApi;
import kakaotech.kangwon3.beforeselling.global.common.ApiResponse;
import kakaotech.kangwon3.beforeselling.global.common.CommonResponseCode;
import kakaotech.kangwon3.beforeselling.global.exception.BaseException;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.UUID;

// /internal/** 는 SecurityConfig의 내부 전용 체인(X-Internal-Token)으로만 인증된다.
@RestController
@RequestMapping("/internal/v1/ai/products")
@RequiredArgsConstructor
public class AiCallbackController implements AiCallbackApi {

    private final AiCallbackUseCase aiCallbackUseCase;

    // AI 진단 콜백. eventType별 하위 이벤트로 나눠 처리한다.
    // 경로의 productId는 URL·문서용이고, 처리는 본문(event)의 productId를 기준으로 한다.
    @Override
    @PostMapping("/{productId}")
    public ResponseEntity<ApiResponse<Void>> receiveCallback(
            @PathVariable UUID productId,
            @Valid @RequestBody ProductEvent event
    ) {
        switch (event) {
            case ProductResultEvent result -> aiCallbackUseCase.handleResult(result);
            // TODO: 진행·질문·실패 콜백 처리. 구현하면 아래 throw를 지우고 주석을 푼다.
            //  받은 척(200) 하면 AI가 전달된 것으로 보고 다시 보내지 않으므로, 처리 전까지는 400으로 거절해 로그에 남긴다.
            case ProductProgressEvent progress -> aiCallbackUseCase.handleProgress(progress);
            // case ProductAwaitingInputEvent awaitingInput -> aiCallbackUseCase.handleAwaitingInput(awaitingInput);
            // case ProductFailedEvent failed -> aiCallbackUseCase.handleFailed(failed);
            case ProductAwaitingInputEvent awaitingInput -> throw new BaseException(CommonResponseCode.BAD_REQUEST);
            case ProductFailedEvent failed -> throw new BaseException(CommonResponseCode.BAD_REQUEST);
        }

        return ResponseEntity.ok(ApiResponse.ofSuccess(CommonResponseCode.OK));
    }
}
