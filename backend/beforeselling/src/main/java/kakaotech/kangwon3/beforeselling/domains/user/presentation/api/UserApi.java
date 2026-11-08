package kakaotech.kangwon3.beforeselling.domains.user.presentation.api;

import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.servlet.http.HttpServletResponse;
import jakarta.validation.Valid;
import kakaotech.kangwon3.beforeselling.domains.user.application.dto.request.NotificationSettingModifyRequest;
import kakaotech.kangwon3.beforeselling.domains.user.application.dto.request.UserProfileModifyRequest;
import kakaotech.kangwon3.beforeselling.domains.user.application.dto.response.NotificationSettingResponse;
import kakaotech.kangwon3.beforeselling.domains.user.application.dto.response.UserProfileResponse;
import kakaotech.kangwon3.beforeselling.global.annotation.swagger.ApiErrorResponseExplanation;
import kakaotech.kangwon3.beforeselling.global.annotation.swagger.ApiResponseExplanations;
import kakaotech.kangwon3.beforeselling.global.annotation.swagger.ApiSuccessResponseExplanation;
import kakaotech.kangwon3.beforeselling.global.common.ApiResponse;
import kakaotech.kangwon3.beforeselling.global.common.CommonResponseCode;
import kakaotech.kangwon3.beforeselling.global.security.principal.UserPrincipal;
import org.springframework.http.ResponseEntity;

@Tag(name = "User", description = "회원 API")
public interface UserApi {

    @Operation(
            summary = "내 정보 조회",
            description = "로그인한 회원의 이름, 이메일, 소셜 제공자를 조회합니다. 소셜 계정에서 이메일을 받지 못한 회원은 `email`이 `null`입니다.")
    @ApiResponseExplanations(
            success = @ApiSuccessResponseExplanation(responseClass = UserProfileResponse.class, description = "조회 성공"),
            errors = {
                    @ApiErrorResponseExplanation(exceptionCode = CommonResponseCode.class, name = "NOT_FOUND"),
            }
    )
    ResponseEntity<ApiResponse<UserProfileResponse>> getMyProfile(
            @Parameter(hidden = true) UserPrincipal principal);

    @Operation(
            summary = "내 정보 수정",
            description = """
                    로그인한 회원의 이름을 수정하고, 수정된 정보를 반환합니다.
                    - `name`을 보내지 않거나 `null`이면 이름을 바꾸지 않습니다.
                    - `name`은 앞뒤 공백을 제거해 저장하며, 공백만 있거나 20자를 넘으면 `INVALID_METHOD_ARGUMENT`입니다.
                    - 이메일은 수정할 수 없습니다.
                    """)
    @ApiResponseExplanations(
            success = @ApiSuccessResponseExplanation(responseClass = UserProfileResponse.class, description = "수정 성공"),
            errors = {
                    @ApiErrorResponseExplanation(exceptionCode = CommonResponseCode.class, name = "INVALID_METHOD_ARGUMENT"),
                    @ApiErrorResponseExplanation(exceptionCode = CommonResponseCode.class, name = "NOT_FOUND"),
            }
    )
    ResponseEntity<ApiResponse<UserProfileResponse>> modifyMyProfile(
            @Parameter(hidden = true) UserPrincipal principal,
            @Valid UserProfileModifyRequest request);

    @Operation(
            summary = "내 알림 설정 조회",
            description = """
                    로그인한 회원의 알림 설정을 조회합니다.
                    - `lawAmendmentAlertEnabled`: 개정 알림(마이페이지 배너·메일) 수신 여부. 가입 시 `true`입니다.
                    """)
    @ApiResponseExplanations(
            success = @ApiSuccessResponseExplanation(responseClass = NotificationSettingResponse.class, description = "조회 성공"),
            errors = {
                    @ApiErrorResponseExplanation(exceptionCode = CommonResponseCode.class, name = "NOT_FOUND"),
            }
    )
    ResponseEntity<ApiResponse<NotificationSettingResponse>> getMyNotificationSetting(
            @Parameter(hidden = true) UserPrincipal principal);

    @Operation(
            summary = "내 알림 설정 수정",
            description = """
                    로그인한 회원의 알림 설정을 바꾸고, 바뀐 설정을 반환합니다.
                    - `lawAmendmentAlertEnabled`를 `false`로 바꾸면 개정 알림 조회가 빈 목록이 되고 개정 알림 메일도 받지 않습니다.
                    - `lawAmendmentAlertEnabled`가 없거나 `null`이면 `INVALID_METHOD_ARGUMENT`입니다.
                    """)
    @ApiResponseExplanations(
            success = @ApiSuccessResponseExplanation(responseClass = NotificationSettingResponse.class, description = "수정 성공"),
            errors = {
                    @ApiErrorResponseExplanation(exceptionCode = CommonResponseCode.class, name = "INVALID_METHOD_ARGUMENT"),
                    @ApiErrorResponseExplanation(exceptionCode = CommonResponseCode.class, name = "NOT_FOUND"),
            }
    )
    ResponseEntity<ApiResponse<NotificationSettingResponse>> modifyMyNotificationSetting(
            @Parameter(hidden = true) UserPrincipal principal,
            @Valid NotificationSettingModifyRequest request);

    @Operation(
            summary = "회원 탈퇴",
            description = """
                    회원 정보를 삭제하고 현재 세션의 리프레시 토큰을 폐기합니다.
                    같은 소셜 계정으로 다시 로그인하면 새 회원으로 자동 가입됩니다.
                    """)
    @ApiResponseExplanations(
            success = @ApiSuccessResponseExplanation(responseCode = CommonResponseCode.NO_CONTENT, description = "탈퇴 성공")
    )
    ResponseEntity<Void> withdraw(
            @Parameter(hidden = true) UserPrincipal principal,
            @Parameter(hidden = true) String refreshToken,
            @Parameter(hidden = true) HttpServletResponse response);
}
