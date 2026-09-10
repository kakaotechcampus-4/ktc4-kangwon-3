package kakaotech.kangwon3.beforeselling.global.infra.s3.presentation.api;

import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import kakaotech.kangwon3.beforeselling.global.annotation.swagger.ApiErrorResponseExplanation;
import kakaotech.kangwon3.beforeselling.global.annotation.swagger.ApiResponseExplanations;
import kakaotech.kangwon3.beforeselling.global.annotation.swagger.ApiSuccessResponseExplanation;
import kakaotech.kangwon3.beforeselling.global.common.ApiResponse;
import kakaotech.kangwon3.beforeselling.global.infra.s3.FileResponseCode;
import kakaotech.kangwon3.beforeselling.global.infra.s3.dto.PresignedUrlRequest;
import kakaotech.kangwon3.beforeselling.global.infra.s3.dto.PresignedUrlResponse;
import kakaotech.kangwon3.beforeselling.global.security.principal.UserPrincipal;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.RequestBody;

@Tag(name = "Presigned URL", description = "S3 업로드용 Presigned URL 발급 API.")
public interface S3PresignApi {

    @Operation(
            summary = "Presigned URL 발급",
            description = """
                    업로드할 파일 정보를 전달하면 S3에 직접 업로드할 수 있는 Presigned PUT URL을 발급합니다.
                    클라이언트는 발급받은 presignedUrl로 PUT 요청을 보내 파일을 업로드하고,
                    업로드 완료 후에는 함께 반환된 fileUrl로 파일에 접근합니다.

                    PUT 요청은 S3로 직접 전송되므로 아래 오류는 이 API의 응답이 아닌 S3의 응답이며,
                    이 API의 응답 규격(ApiResponse)을 따르지 않고 S3가 반환하는 XML 오류 응답 형태로 내려옵니다.
                    - 403 Forbidden (AccessDenied, "Request has expired"): presignedUrl 유효시간(발급 시점 기준 5분) 초과 후 업로드를 시도한 경우
                    - 403 Forbidden (SignatureDoesNotMatch): 업로드 요청의 Content-Type/Content-Length가 발급 시 지정한 값과 다르거나, presignedUrl을 변형하거나 다른 HTTP 메서드로 호출한 경우
                    - 403 Forbidden (AccessDenied): 버킷 정책/자격 증명 등 인프라 설정 문제
                    """)
    @ApiResponseExplanations(
            success = @ApiSuccessResponseExplanation(responseClass = PresignedUrlResponse.class, description = "발급 성공"),
            errors = {
                    @ApiErrorResponseExplanation(exceptionCode = FileResponseCode.class, name = "NOT_SUPPORTED_EXTENSION"),
                    @ApiErrorResponseExplanation(exceptionCode = FileResponseCode.class, name = "NOT_SUPPORTED_CONTENT_TYPE"),
                    @ApiErrorResponseExplanation(exceptionCode = FileResponseCode.class, name = "EXCEED_FILE_SIZE"),
            }
    )
    ResponseEntity<ApiResponse<PresignedUrlResponse>> issuePresignedUrls(
            @Parameter(hidden = true) UserPrincipal principal,
            @RequestBody @Valid PresignedUrlRequest request);
}
