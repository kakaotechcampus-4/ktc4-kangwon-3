package kakaotech.kangwon3.beforeselling.global.infra.s3;

import kakaotech.kangwon3.beforeselling.global.config.properties.S3Properties;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;
import software.amazon.awssdk.services.s3.S3Client;
import software.amazon.awssdk.services.s3.model.Delete;
import software.amazon.awssdk.services.s3.model.DeleteObjectsRequest;
import software.amazon.awssdk.services.s3.model.ObjectIdentifier;

import java.util.List;

/**
 * S3 객체를 일괄 삭제한다. DeleteObjects API는 1회 요청당 최대 1000개의 key만 처리하므로 청크 단위로 나눠 호출한다.
 */
@Component
@RequiredArgsConstructor
public class S3ObjectDeleter {

    private static final int MAX_KEYS_PER_REQUEST = 1000;

    private final S3Client s3Client;
    private final S3Properties s3Properties;

    public void deleteAll(List<String> keys) {
        for (int i = 0; i < keys.size(); i += MAX_KEYS_PER_REQUEST) {
            List<String> chunk = keys.subList(i, Math.min(i + MAX_KEYS_PER_REQUEST, keys.size()));
            deleteChunk(chunk);
        }
    }

    private void deleteChunk(List<String> keys) {
        List<ObjectIdentifier> objectIdentifiers = keys.stream()
                .map(key -> ObjectIdentifier.builder().key(key).build())
                .toList();

        DeleteObjectsRequest request = DeleteObjectsRequest.builder()
                .bucket(s3Properties.bucket())
                .delete(Delete.builder().objects(objectIdentifiers).build())
                .build();

        s3Client.deleteObjects(request);
    }
}
