package kakaotech.kangwon3.beforeselling.domains.diagnoses.presentation.controller;

import jakarta.validation.Valid;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.request.DiagnosesCreateRequest;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.DiagnosesCreateResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.DiagnosesDetailResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.usecase.DiagnosesUseCase;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.presentation.api.DiagnosesApi;
import kakaotech.kangwon3.beforeselling.global.common.ApiResponse;
import kakaotech.kangwon3.beforeselling.global.common.CommonResponseCode;
import kakaotech.kangwon3.beforeselling.global.security.annotation.LoginUser;
import kakaotech.kangwon3.beforeselling.global.security.principal.UserPrincipal;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.ResponseEntity;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.*;

@Slf4j
@RestController
@Validated
@RequestMapping("/api/v1/diagnoses")
@RequiredArgsConstructor
public class DiagnosesController implements DiagnosesApi {

    private final DiagnosesUseCase diagnosesUseCase;

    // 신규 상품 진단 요청(진단서는 PENDING 상태로 생성)
    @Override
    @PostMapping
    public ResponseEntity<ApiResponse<DiagnosesCreateResponse>> createDiagnoses(
            @LoginUser UserPrincipal principal,
            @Valid @RequestBody DiagnosesCreateRequest request
    ) {
        DiagnosesCreateResponse response = diagnosesUseCase.createDiagnoses(principal.userId(), request);

        return ResponseEntity.ok(ApiResponse.ofSuccess(CommonResponseCode.OK, response));
    }

    // 진단서 단건 조회
    @Override
    @GetMapping("/{diagnosesId}")
    public ResponseEntity<ApiResponse<DiagnosesDetailResponse>> getDiagnoses(
            @LoginUser UserPrincipal principal,
            @PathVariable Long diagnosesId
    ) {
        DiagnosesDetailResponse response = diagnosesUseCase.getDiagnoses(principal.userId(), diagnosesId);

        return ResponseEntity.ok(ApiResponse.ofSuccess(CommonResponseCode.OK, response));
    }

    // 진단서 단건 삭제
    @Override
    @DeleteMapping("/{diagnosesId}")
    public ResponseEntity<ApiResponse<Void>> removeDiagnoses(
            @LoginUser UserPrincipal principal,
            @PathVariable Long diagnosesId
    ) {
        diagnosesUseCase.removeDiagnoses(principal.userId(), diagnosesId);

        return ResponseEntity.ok(ApiResponse.ofSuccess(CommonResponseCode.OK));
    }
}
