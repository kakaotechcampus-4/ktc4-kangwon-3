package kakaotech.kangwon3.beforeselling.global.infra.s3.dto;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Positive;
import jakarta.validation.constraints.Size;
import kakaotech.kangwon3.beforeselling.global.infra.s3.FileType;

import java.util.List;

public record PresignedUrlRequest(
        @NotEmpty @Valid List<FileMeta> files
) {

    public record FileMeta(
            @NotNull FileType type,
            @NotBlank @Size(max = 255, message = "파일명이 너무 깁니다.") String fileName,
            @Positive long fileSize
    ) {
    }
}
