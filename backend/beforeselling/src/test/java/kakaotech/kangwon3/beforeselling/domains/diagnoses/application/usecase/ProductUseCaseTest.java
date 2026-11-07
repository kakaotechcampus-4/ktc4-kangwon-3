package kakaotech.kangwon3.beforeselling.domains.diagnoses.application.usecase;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.mapper.ProductMapper;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.service.ProductService;
import kakaotech.kangwon3.beforeselling.domains.lawamendment.domain.service.LawAmendmentService;
import kakaotech.kangwon3.beforeselling.global.common.CommonResponseCode;
import kakaotech.kangwon3.beforeselling.global.exception.BaseException;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.BDDMockito.never;
import static org.mockito.BDDMockito.then;
import static org.mockito.BDDMockito.willThrow;

@ExtendWith(MockitoExtension.class)
class ProductUseCaseTest {

    private static final UUID USER_ID = UUID.randomUUID();
    private static final UUID PRODUCT_ID = UUID.randomUUID();

    @Mock
    private ProductService productService;

    @Mock
    private ProductMapper productMapper;

    @Mock
    private LawAmendmentService lawAmendmentService;

    @InjectMocks
    private ProductUseCase productUseCase;

    @Test
    @DisplayName("상품을 재진단하면 재확인 대상에서 그 상품을 뺀다.")
    void rediagnoseProduct_thenRemoveRecheckProducts() {
        // when
        productUseCase.rediagnoseProduct(USER_ID, PRODUCT_ID);

        // then
        then(productService).should().rediagnoseProduct(USER_ID, PRODUCT_ID);
        then(lawAmendmentService).should().removeRecheckProducts(PRODUCT_ID);
    }

    @Test
    @DisplayName("재진단할 수 없는 상품이면 재확인 대상에 그대로 남긴다.")
    void rediagnoseProduct_whenConflict_thenKeepRecheckProducts() {
        // given
        willThrow(new BaseException(CommonResponseCode.CONFLICT))
                .given(productService).rediagnoseProduct(USER_ID, PRODUCT_ID);

        // when & then
        assertThatThrownBy(() -> productUseCase.rediagnoseProduct(USER_ID, PRODUCT_ID))
                .isInstanceOf(BaseException.class);
        then(lawAmendmentService).should(never()).removeRecheckProducts(any());
    }
}
