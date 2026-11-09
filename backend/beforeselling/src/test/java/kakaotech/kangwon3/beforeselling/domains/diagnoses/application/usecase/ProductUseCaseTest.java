package kakaotech.kangwon3.beforeselling.domains.diagnoses.application.usecase;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.mapper.ProductMapper;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.service.ProductService;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.UUID;

import static org.mockito.BDDMockito.then;

@ExtendWith(MockitoExtension.class)
class ProductUseCaseTest {

    private static final UUID USER_ID = UUID.randomUUID();
    private static final UUID PRODUCT_ID = UUID.randomUUID();

    @Mock
    private ProductService productService;

    @Mock
    private ProductMapper productMapper;

    @InjectMocks
    private ProductUseCase productUseCase;

    @Test
    @DisplayName("상품 재진단은 ProductService에 맡긴다. 재확인 대상 해제는 재진단 이벤트 리스너가 한다.")
    void rediagnoseProduct_thenDelegateToProductService() {
        // when
        productUseCase.rediagnoseProduct(USER_ID, PRODUCT_ID);

        // then
        then(productService).should().rediagnoseProduct(USER_ID, PRODUCT_ID);
    }
}
