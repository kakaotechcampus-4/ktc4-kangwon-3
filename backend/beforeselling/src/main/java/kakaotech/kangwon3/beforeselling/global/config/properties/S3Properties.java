package kakaotech.kangwon3.beforeselling.global.config.properties;

import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.util.unit.DataSize;

import java.time.Duration;
import java.util.List;

@ConfigurationProperties(prefix = "aws.s3")
public record S3Properties(
        String accessKey,
        String secretKey,
        String bucket,
        String region,
        Duration presignedUrlExpiration,
        DataSize maxFileSize,
        List<String> allowedExtensions
) {
}
