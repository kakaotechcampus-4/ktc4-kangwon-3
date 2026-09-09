package kakaotech.kangwon3.beforeselling.global.infra.s3;

import kakaotech.kangwon3.beforeselling.global.config.properties.S3Properties;
import kakaotech.kangwon3.beforeselling.global.exception.BaseException;
import kakaotech.kangwon3.beforeselling.global.infra.s3.dto.PresignedUrlRequest.FileMeta;
import kakaotech.kangwon3.beforeselling.global.infra.s3.dto.PresignedUrlResponse;
import kakaotech.kangwon3.beforeselling.global.infra.s3.dto.PresignedUrlResponse.PresignedFile;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;
import software.amazon.awssdk.services.s3.model.PutObjectRequest;
import software.amazon.awssdk.services.s3.presigner.S3Presigner;
import software.amazon.awssdk.services.s3.presigner.model.PresignedPutObjectRequest;
import software.amazon.awssdk.services.s3.presigner.model.PutObjectPresignRequest;

import java.util.List;
import java.util.Locale;
import java.util.UUID;

/**
 * S3 Presigned PUT URL 발급을 담당한다. 확장자/크기 검증과 S3 key 조립까지 함께 처리한다.
 */
@Component
@RequiredArgsConstructor
public class S3PresignedUrlProvider {

    private static final String KEY_DELIMITER = "/";

    private final S3Presigner s3Presigner;
    private final S3Properties s3Properties;

    public PresignedUrlResponse issuePresignedUrls(Long userId, List<FileMeta> files) {
        List<PresignedFile> presignedFiles = files.stream()
                .map(file -> issuePresignedUrl(userId, file))
                .toList();

        return new PresignedUrlResponse(presignedFiles);
    }

    private PresignedFile issuePresignedUrl(Long userId, FileMeta file) {
        validateExtension(file.fileName());
        validateFileSize(file.fileSize());

        String key = createKey(userId, file.type(), file.fileName());
        String presignedUrl = presign(key, file.contentType(), file.fileSize());
        String fileUrl = createFileUrl(key);

        return new PresignedFile(file.fileName(), presignedUrl, fileUrl);
    }

    private void validateExtension(String fileName) {
        String extension = StringUtils.getFilenameExtension(fileName);
        if (extension == null || !s3Properties.allowedExtensions().contains(extension.toLowerCase(Locale.ROOT))) {
            throw new BaseException(FileResponseCode.NOT_SUPPORTED_EXTENSION);
        }
    }

    private void validateFileSize(long fileSize) {
        if (fileSize > s3Properties.maxFileSize().toBytes()) {
            throw new BaseException(FileResponseCode.EXCEED_FILE_SIZE);
        }
    }

    private String createKey(Long userId, FileType type, String fileName) {
        String sanitizedFileName = StringUtils.getFilename(fileName);
        String uniqueFileName = "%s_%s".formatted(UUID.randomUUID(), sanitizedFileName);
        return String.join(KEY_DELIMITER, type.getFolderName(), String.valueOf(userId), uniqueFileName);
    }

    private String presign(String key, String contentType, long fileSize) {
        PutObjectRequest objectRequest = PutObjectRequest.builder()
                .bucket(s3Properties.bucket())
                .key(key)
                .contentType(contentType)
                .contentLength(fileSize)
                .build();

        PutObjectPresignRequest presignRequest = PutObjectPresignRequest.builder()
                .signatureDuration(s3Properties.presignedUrlExpiration())
                .putObjectRequest(objectRequest)
                .build();

        PresignedPutObjectRequest presigned = s3Presigner.presignPutObject(presignRequest);
        return presigned.url().toString();
    }

    private String createFileUrl(String key) {
        return "https://%s.s3.%s.amazonaws.com/%s".formatted(s3Properties.bucket(), s3Properties.region(), key);
    }
}
