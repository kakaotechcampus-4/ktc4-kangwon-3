package kakaotech.kangwon3.beforeselling.global.infra.s3;

import lombok.Getter;
import lombok.RequiredArgsConstructor;

@Getter
@RequiredArgsConstructor
public enum FileType {

    PRODUCT_MAIN("product-main"),
    PRODUCT_DETAIL("product-detail"),
    ;

    private final String folderName;
}
