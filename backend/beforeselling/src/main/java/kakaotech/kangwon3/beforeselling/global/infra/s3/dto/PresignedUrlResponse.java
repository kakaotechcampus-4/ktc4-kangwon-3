package kakaotech.kangwon3.beforeselling.global.infra.s3.dto;

import java.util.List;

public record PresignedUrlResponse(
        List<PresignedFile> files
) {

    public record PresignedFile(
            String fileName,
            String presignedUrl,
            String fileUrl
    ) {
    }
}
