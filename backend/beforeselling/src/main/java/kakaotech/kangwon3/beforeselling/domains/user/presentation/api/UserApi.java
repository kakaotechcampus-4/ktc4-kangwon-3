package kakaotech.kangwon3.beforeselling.domains.user.presentation.api;

import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.media.Content;
import io.swagger.v3.oas.annotations.media.Schema;
import io.swagger.v3.oas.annotations.responses.ApiResponses;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.servlet.http.HttpServletResponse;
import kakaotech.kangwon3.beforeselling.global.common.ApiResponse;
import kakaotech.kangwon3.beforeselling.global.security.principal.UserPrincipal;
import org.springframework.http.ResponseEntity;

@Tag(name = "User", description = "회원 API")
public interface UserApi {

    @Operation(
            summary = "회원 탈퇴",
            description = """
                    회원 정보를 삭제하고 현재 세션의 리프레시 토큰을 폐기합니다.
                    같은 소셜 계정으로 다시 로그인하면 새 회원으로 자동 가입됩니다.
                    """)
    @ApiResponses({
            @io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "200", description = "탈퇴 성공"),
            @io.swagger.v3.oas.annotations.responses.ApiResponse(responseCode = "401",
                    description = "COMMON-004: 인증 없음 / AUTH-001: 액세스 토큰 만료 / AUTH-002: 액세스 토큰 무효",
                    content = @Content(schema = @Schema(implementation = ApiResponse.class))),
    })
    ResponseEntity<ApiResponse<Void>> withdraw(
            @Parameter(hidden = true) UserPrincipal principal,
            @Parameter(hidden = true) String refreshToken,
            @Parameter(hidden = true) HttpServletResponse response);
}
