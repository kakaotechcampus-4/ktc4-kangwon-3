package kakaotech.kangwon3.beforeselling.global.infra.s3;

import kakaotech.kangwon3.beforeselling.global.config.properties.S3Properties;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;
import software.amazon.awssdk.core.exception.SdkException;
import software.amazon.awssdk.services.s3.S3Client;
import software.amazon.awssdk.services.s3.model.CopyObjectRequest;
import software.amazon.awssdk.services.s3.model.DeleteObjectRequest;

import java.util.List;

/**
 * presigned URL로 temp/ 경로에 업로드된 파일을, 엔티티 생성이 확정된 시점에 정식 경로로 옮긴다.
 * 이미지는 URL이 아닌 S3 key로 저장되므로 key만 다루고 URL 변환은 하지 않는다.
 * 여러 건을 이동하다 일부가 실패하면 이미 이동된 파일은 그대로 두고 예외만 전파한다
 * (롤백을 시도하지 않음 — API 응답 지연을 만들지 않기 위함. temp에 남은 원본은 Lifecycle Rule이 정리한다).
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class S3FileMover {

    private static final String TEMP_PREFIX = "temp/";

    private final S3Client s3Client;
    private final S3Properties s3Properties;

    public String moveToPermanent(String tempKey) {
        if (!StringUtils.hasText(tempKey)) {
            return tempKey;
        }

        if (!tempKey.startsWith(TEMP_PREFIX)) {
            log.warn("temp 경로가 아니어서 이동을 건너뜁니다. key={}", tempKey);
            return tempKey;
        }

        String permanentKey = tempKey.substring(TEMP_PREFIX.length());
        try {
            s3Client.copyObject(CopyObjectRequest.builder()
                    .sourceBucket(s3Properties.bucket())
                    .sourceKey(tempKey)
                    .destinationBucket(s3Properties.bucket())
                    .destinationKey(permanentKey)
                    .build());
            s3Client.deleteObject(DeleteObjectRequest.builder()
                    .bucket(s3Properties.bucket())
                    .key(tempKey)
                    .build());
        } catch (SdkException e) {
            log.error("S3 파일 이동에 실패했습니다. tempKey={}, permanentKey={}", tempKey, permanentKey, e);
            throw e;
        }

        return permanentKey;
    }

    public List<String> moveAllToPermanent(List<String> tempKeys) {
        if (tempKeys == null) {
            return null;
        }
        return tempKeys.stream().map(this::moveToPermanent).toList();
    }
}
