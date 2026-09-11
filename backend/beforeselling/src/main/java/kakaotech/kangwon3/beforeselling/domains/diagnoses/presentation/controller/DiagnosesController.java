package kakaotech.kangwon3.beforeselling.domains.diagnoses.presentation.controller;

import jakarta.validation.Valid;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.request.DiagnosesCreateRequest;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.request.DiagnosesSortType;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.DiagnosesDetailResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.DiagnosesListResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.usecase.DiagnosesUseCase;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ResultStatus;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.presentation.api.DiagnosesApi;
import kakaotech.kangwon3.beforeselling.global.common.ApiResponse;
import kakaotech.kangwon3.beforeselling.global.common.CommonResponseCode;
import kakaotech.kangwon3.beforeselling.global.security.annotation.LoginUser;
import kakaotech.kangwon3.beforeselling.global.security.principal.UserPrincipal;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@Slf4j
@RestController
@RequestMapping("/api/v1/diagnoses")
@RequiredArgsConstructor
public class DiagnosesController implements DiagnosesApi {

    private final DiagnosesUseCase diagnosesUseCase;

    // 신규 상품 진단 요청(진단서는 PENDING 상태로 생성)
    @Override
    @PostMapping
    public ResponseEntity<ApiResponse<Void>> createDiagnoses(
            @LoginUser UserPrincipal principal,
            @Valid @RequestBody DiagnosesCreateRequest request
    ) {
        diagnosesUseCase.createDiagnoses(principal.userId(), request);

        return ResponseEntity.ok(ApiResponse.ofSuccess(CommonResponseCode.OK));
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

    // 마이페이지 진단서 목록 조회(페이징, 정렬, 결과 필터 적용)
    @Override
    @GetMapping
    public ResponseEntity<ApiResponse<DiagnosesListResponse>> getDiagnosesList(
            @LoginUser UserPrincipal principal,
            @RequestParam(required = false) ResultStatus resultStatus,
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "10") int size,
            @RequestParam(defaultValue = "LATEST") DiagnosesSortType sortType
    ) {
        Pageable pageable = PageRequest.of(page, size, sortType.getSort());
        DiagnosesListResponse response = diagnosesUseCase.getDiagnosesList(principal.userId(), resultStatus, pageable);

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
