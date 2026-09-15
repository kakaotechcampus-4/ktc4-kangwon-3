package kakaotech.kangwon3.beforeselling.global.infra.s3;

import kakaotech.kangwon3.beforeselling.global.config.properties.S3Properties;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;
import org.springframework.web.util.UriUtils;

import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import java.util.stream.Collectors;

/**
 * S3 key를 발급된 fileUrl로 인코딩한다. presign 발급 외의 컴포넌트도 같은 인코딩 규칙을
 * 재사용할 수 있도록 이 클래스에서만 관리한다.
 */
@Component
@RequiredArgsConstructor
public class S3UrlKeyCodec {

    private static final String URL_PREFIX_TEMPLATE = "https://%s.s3.%s.amazonaws.com/";
    private static final String KEY_DELIMITER = "/";

    private final S3Properties s3Properties;

    public String toUrl(String key) {
        String encodedKey = Arrays.stream(key.split(KEY_DELIMITER))
                .map(segment -> UriUtils.encodePathSegment(segment, StandardCharsets.UTF_8))
                .collect(Collectors.joining(KEY_DELIMITER));
        return urlPrefix() + encodedKey;
    }

    public String toUrlOrNull(String key) {
        return key == null ? null : toUrl(key);
    }

    private String urlPrefix() {
        return URL_PREFIX_TEMPLATE.formatted(s3Properties.bucket(), s3Properties.region());
    }
}
