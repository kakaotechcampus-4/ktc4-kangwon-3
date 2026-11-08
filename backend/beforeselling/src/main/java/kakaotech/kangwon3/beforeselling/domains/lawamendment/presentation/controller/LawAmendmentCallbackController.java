package kakaotech.kangwon3.beforeselling.domains.lawamendment.presentation.controller;

import jakarta.validation.Valid;
import kakaotech.kangwon3.beforeselling.domains.lawamendment.application.dto.callback.LawChangeCallbackRequest;
import kakaotech.kangwon3.beforeselling.domains.lawamendment.application.usecase.LawAmendmentCallbackUseCase;
import kakaotech.kangwon3.beforeselling.domains.lawamendment.presentation.api.LawAmendmentCallbackApi;
import kakaotech.kangwon3.beforeselling.global.common.ApiResponse;
import kakaotech.kangwon3.beforeselling.global.common.CommonResponseCode;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/internal/v1/ai/law-changes")
@RequiredArgsConstructor
public class LawAmendmentCallbackController implements LawAmendmentCallbackApi {

    private final LawAmendmentCallbackUseCase lawAmendmentCallbackUseCase;

    @Override
    @PostMapping
    public ResponseEntity<ApiResponse<Void>> receiveLawChanges(@Valid @RequestBody LawChangeCallbackRequest request) {
        lawAmendmentCallbackUseCase.receiveLawChanges(request);

        return ResponseEntity.ok(ApiResponse.ofSuccess(CommonResponseCode.OK));
    }
}
