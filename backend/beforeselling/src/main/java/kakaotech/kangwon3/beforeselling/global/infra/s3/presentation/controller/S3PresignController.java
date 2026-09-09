package kakaotech.kangwon3.beforeselling.global.infra.s3.presentation.controller;

import jakarta.validation.Valid;
import kakaotech.kangwon3.beforeselling.global.common.ApiResponse;
import kakaotech.kangwon3.beforeselling.global.common.CommonResponseCode;
import kakaotech.kangwon3.beforeselling.global.infra.s3.S3PresignedUrlProvider;
import kakaotech.kangwon3.beforeselling.global.infra.s3.dto.PresignedUrlRequest;
import kakaotech.kangwon3.beforeselling.global.infra.s3.dto.PresignedUrlResponse;
import kakaotech.kangwon3.beforeselling.global.infra.s3.presentation.api.S3PresignApi;
import kakaotech.kangwon3.beforeselling.global.security.annotation.LoginUser;
import kakaotech.kangwon3.beforeselling.global.security.principal.UserPrincipal;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1")
@RequiredArgsConstructor
public class S3PresignController implements S3PresignApi {

    private final S3PresignedUrlProvider s3PresignedUrlProvider;

    @Override
    @PostMapping("/presigned-url")
    public ResponseEntity<ApiResponse<PresignedUrlResponse>> issuePresignedUrls(
            @LoginUser UserPrincipal principal,
            @Valid @RequestBody PresignedUrlRequest request
    ) {
        PresignedUrlResponse response = s3PresignedUrlProvider.issuePresignedUrls(principal.userId(), request.files());
        return ResponseEntity.ok(ApiResponse.ofSuccess(CommonResponseCode.OK, response));
    }
}
