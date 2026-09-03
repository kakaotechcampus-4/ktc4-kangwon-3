package kakaotech.kangwon3.beforeselling.domains.auth.presentation.api;

import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.media.Content;
import io.swagger.v3.oas.annotations.media.Schema;
import io.swagger.v3.oas.annotations.responses.ApiResponses;
import io.swagger.v3.oas.annotations.security.SecurityRequirements;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.servlet.http.HttpServletResponse;
import kakaotech.kangwon3.beforeselling.domains.auth.application.dto.response.TokenResponse;
import kakaotech.kangwon3.beforeselling.global.common.ApiResponse;
import kakaotech.kangwon3.beforeselling.global.security.principal.UserPrincipal;
import org.springframework.http.ResponseEntity;

@Tag(name = "Auth", description = """
        인증 API.
        소셜 로그인 시작은 브라우저에서 `GET /oauth2/authorization/{kakao|naver|google}` 로 이동합니다.
        성공 시 `refresh_token` HttpOnly 쿠키가 설정되고 프론트엔드 콜백 URL로 리다이렉트되며,
        프론트엔드는 이어서 `POST /api/v1/auth/reissue` 로 액세스 토큰을 획득합니다.
        """)
public interface AuthApi {

    @Operation(
            summary = "액세스 토큰 재발급",
            description = """
                    `refresh_token` 쿠키로 액세스 토큰을 재발급합니다. 리프레시 토큰도 함께 회전되어 새 쿠키로 내려갑니다.
                    이전 리프레시 토큰을 재사용하면 `AUTH-003`이 응답되며, 이 경우 재로그인이 필요합니다.
                    """)
    @ApiResponses({
            @io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "200", description = "재발급 성공"),
            @io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "401",
                    description = "AUTH-003: 리프레시 토큰 없음/만료/폐기/변조",
                    content = @Content(schema = @Schema(implementation = ApiResponse.class))),
    })
    @SecurityRequirements
    ResponseEntity<ApiResponse<TokenResponse>> reissueToken(
            @Parameter(hidden = true) String refreshToken,
            @Parameter(hidden = true) HttpServletResponse response);

    @Operation(
            summary = "로그아웃",
            description = "리프레시 토큰을 폐기하고 쿠키를 만료시킵니다. 액세스 토큰은 만료 전까지 유효하므로 클라이언트에서 즉시 삭제해야 합니다.")
    @ApiResponses({
            @io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "200", description = "로그아웃 성공"),
            @io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "401",
                    description = "COMMON-008: 인증 없음 / AUTH-001: 액세스 토큰 만료 / AUTH-002: 액세스 토큰 무효",
                    content = @Content(schema = @Schema(implementation = ApiResponse.class))),
    })
    ResponseEntity<ApiResponse<Void>> logout(
            @Parameter(hidden = true) UserPrincipal principal,
            @Parameter(hidden = true) String refreshToken,
            @Parameter(hidden = true) HttpServletResponse response);
}
