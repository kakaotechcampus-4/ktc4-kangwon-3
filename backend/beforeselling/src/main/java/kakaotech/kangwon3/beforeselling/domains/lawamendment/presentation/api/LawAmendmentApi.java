package kakaotech.kangwon3.beforeselling.domains.lawamendment.presentation.api;

import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.tags.Tag;
import kakaotech.kangwon3.beforeselling.domains.lawamendment.application.dto.response.LawAmendmentListResponse;
import kakaotech.kangwon3.beforeselling.global.annotation.swagger.ApiErrorResponseExplanation;
import kakaotech.kangwon3.beforeselling.global.annotation.swagger.ApiResponseExplanations;
import kakaotech.kangwon3.beforeselling.global.annotation.swagger.ApiSuccessResponseExplanation;
import kakaotech.kangwon3.beforeselling.global.common.ApiResponse;
import kakaotech.kangwon3.beforeselling.global.common.CommonResponseCode;
import kakaotech.kangwon3.beforeselling.global.security.principal.UserPrincipal;
import org.springframework.http.ResponseEntity;

@Tag(name = "Law Amendments", description = "법령 개정 API. 진단 근거 법령이 바뀌어 다시 확인해야 하는 상품을 알려 줍니다.")
public interface LawAmendmentApi {

    @Operation(
            summary = "재확인 대상 상품 조회",
            description = """
                    로그인한 회원의 재확인 대상 상품을 법령 개정별로 묶어 조회합니다. (마이페이지 개정 알림 배너)
                    진단 근거 법령의 적용 판이 바뀌면, 그 분야를 검토해 진단을 마친 상품이 재확인 대상(`products`)이 됩니다.

                    - 최근 개정부터, 개정 안에서는 최근 상품부터 담깁니다.
                    - 재확인 대상 상품을 재진단하거나 삭제하면 그 상품은 빠지고, 남은 상품이 없는 개정은 목록에서 빠집니다.
                    - 개정 알림 수신을 끈 회원(`lawAmendmentAlertEnabled`가 `false`)은 빈 목록입니다.
                    - `revisionType`(일부개정 등)과 `enforceDate`(시행일)는 AI가 보내지 않으면 `null`입니다.
                    - 상품의 `diagnosesId`는 그 상품이 속한 진단서 ID입니다. 재진단해도 같은 진단서에서 다시 진단하므로 바뀌지 않아, 재진단 후 진행 화면(`/judgement/{diagnosesId}`)으로 바로 이동할 때 씁니다.
                    """)
    @ApiResponseExplanations(
            success = @ApiSuccessResponseExplanation(responseClass = LawAmendmentListResponse.class, description = "조회 성공"),
            errors = {
                    @ApiErrorResponseExplanation(exceptionCode = CommonResponseCode.class, name = "NOT_FOUND"),
            }
    )
    ResponseEntity<ApiResponse<LawAmendmentListResponse>> getLawAmendments(
            @Parameter(hidden = true) UserPrincipal principal);
}
