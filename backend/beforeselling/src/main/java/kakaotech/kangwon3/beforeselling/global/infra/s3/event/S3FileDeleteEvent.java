package kakaotech.kangwon3.beforeselling.global.infra.s3.event;

import java.util.List;

public record S3FileDeleteEvent(List<String> keys) {
}
