package kakaotech.kangwon3.beforeselling.global.infra.s3.dto;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Positive;
import kakaotech.kangwon3.beforeselling.global.infra.s3.FileType;

import java.util.List;

public record PresignedUrlRequest(
        @NotEmpty @Valid List<FileMeta> files
) {

    public record FileMeta(
            @NotNull FileType type,
            @NotBlank String fileName,
            @NotBlank String contentType,
            @Positive long fileSize
    ) {
    }
}
