package kakaotech.kangwon3.beforeselling.domains.lawamendment.presentation.controller;

import kakaotech.kangwon3.beforeselling.domains.lawamendment.application.dto.response.LawAmendmentListResponse;
import kakaotech.kangwon3.beforeselling.domains.lawamendment.application.usecase.LawAmendmentUseCase;
import kakaotech.kangwon3.beforeselling.domains.lawamendment.presentation.api.LawAmendmentApi;
import kakaotech.kangwon3.beforeselling.global.common.ApiResponse;
import kakaotech.kangwon3.beforeselling.global.common.CommonResponseCode;
import kakaotech.kangwon3.beforeselling.global.security.annotation.LoginUser;
import kakaotech.kangwon3.beforeselling.global.security.principal.UserPrincipal;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/law-amendments")
@RequiredArgsConstructor
public class LawAmendmentController implements LawAmendmentApi {

    private final LawAmendmentUseCase lawAmendmentUseCase;

    @Override
    @GetMapping
    public ResponseEntity<ApiResponse<LawAmendmentListResponse>> getLawAmendments(
            @LoginUser UserPrincipal principal
    ) {
        LawAmendmentListResponse response = lawAmendmentUseCase.getLawAmendments(principal.userId());

        return ResponseEntity.ok(ApiResponse.ofSuccess(CommonResponseCode.OK, response));
    }
}
