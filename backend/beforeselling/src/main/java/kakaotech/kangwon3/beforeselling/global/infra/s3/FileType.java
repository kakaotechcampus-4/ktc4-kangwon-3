package kakaotech.kangwon3.beforeselling.global.infra.s3;

import lombok.Getter;
import lombok.RequiredArgsConstructor;

import java.util.UUID;

@Getter
@RequiredArgsConstructor
public enum FileType {

    PRODUCT_MAIN("product-main"),
    PRODUCT_DETAIL("product-detail"),
    ;

    private static final String KEY_DELIMITER = "/";

    private final String folderName;

    public String keyPrefix(UUID userId) {
        return folderName + KEY_DELIMITER + userId + KEY_DELIMITER;
    }

    public boolean isOwnedBy(String key, UUID userId) {
        String prefix = keyPrefix(userId);
        if (key == null || !key.startsWith(prefix)) {
            return false;
        }
        String fileName = key.substring(prefix.length());
        return !fileName.isEmpty() && !fileName.contains(KEY_DELIMITER);
    }
}
