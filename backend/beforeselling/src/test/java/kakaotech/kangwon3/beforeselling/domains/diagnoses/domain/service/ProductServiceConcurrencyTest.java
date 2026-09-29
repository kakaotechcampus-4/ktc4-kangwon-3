package kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.service;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Diagnoses;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Product;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.SourceType;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.repository.DiagnosesRepository;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.repository.ProductRepository;
import kakaotech.kangwon3.beforeselling.global.common.CommonResponseCode;
import kakaotech.kangwon3.beforeselling.global.exception.BaseException;
import kakaotech.kangwon3.beforeselling.global.infra.s3.S3ObjectDeleter;
import kakaotech.kangwon3.beforeselling.global.infra.s3.domain.service.S3FileService;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.RepeatedTest;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.bean.override.mockito.MockitoBean;

import java.util.ArrayList;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.Callable;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * 실제 트랜잭션을 두 스레드에서 동시에 실행해 removeProduct 의 진단서 락을 검증한다.
 * 타이밍에 따라 경합이 안 날 수도 있어서 여러 번 반복한다.
 */
@SpringBootTest
@ActiveProfiles("test")
class ProductServiceConcurrencyTest {

    private static final UUID USER_ID = UUID.randomUUID();
    private static final String PRODUCT_IMAGE_KEY = "product-main/1/uuid_thumbnail.jpg";
    private static final String SOURCE_URL = "https://ko.aliexpress.com/item/100500628491";
    private static final String SUCCESS = "SUCCESS";

    @Autowired
    private ProductService productService;

    @Autowired
    private DiagnosesRepository diagnosesRepository;

    @Autowired
    private ProductRepository productRepository;

    // 커밋 후 비동기로 실행되는 S3 삭제 리스너가 외부 S3·s3_files 테이블에 접근하지 않게 막는다.
    @MockitoBean
    private S3ObjectDeleter s3ObjectDeleter;

    @MockitoBean
    private S3FileService s3FileService;

    @AfterEach
    void tearDown() {
        diagnosesRepository.deleteAll();
    }

    @RepeatedTest(10)
    @DisplayName("같은 진단서의 서로 다른 상품을 동시에 삭제하면 둘 다 삭제되고 빈 진단서도 삭제된다.")
    void removeProduct_concurrentlyDifferentProducts_thenDeleteDiagnoses() throws Exception {
        // given
        Diagnoses diagnoses = saveDiagnoses("상품 A", "상품 B");
        UUID productA = diagnoses.getProducts().get(0).getId();
        UUID productB = diagnoses.getProducts().get(1).getId();

        // when
        List<String> results = runConcurrently(
                () -> productService.removeProduct(USER_ID, productA),
                () -> productService.removeProduct(USER_ID, productB));

        // then
        assertThat(results).containsOnly(SUCCESS);
        assertThat(productRepository.count()).isZero();
        assertThat(diagnosesRepository.count()).isZero();
    }

    @RepeatedTest(10)
    @DisplayName("같은 상품을 동시에 두 번 삭제하면 하나만 성공하고 나머지는 NOT_FOUND 가 된다.")
    void removeProduct_concurrentlySameProduct_thenOneSucceedsOtherNotFound() throws Exception {
        // given
        Diagnoses diagnoses = saveDiagnoses("상품 A", "상품 B");
        UUID productA = diagnoses.getProducts().get(0).getId();

        // when
        List<String> results = runConcurrently(
                () -> productService.removeProduct(USER_ID, productA),
                () -> productService.removeProduct(USER_ID, productA));

        // then
        assertThat(results).containsExactlyInAnyOrder(SUCCESS, CommonResponseCode.NOT_FOUND.getCode());
        assertThat(productRepository.findAll())
                .extracting(Product::getProductName)
                .containsExactly("상품 B");
        assertThat(diagnosesRepository.count()).isOne();
    }

    @RepeatedTest(10)
    @DisplayName("마지막 상품을 동시에 두 번 삭제하면 하나만 성공하고 진단서도 삭제된다.")
    void removeProduct_concurrentlyLastProduct_thenOneSucceedsAndDeleteDiagnoses() throws Exception {
        // given
        Diagnoses diagnoses = saveDiagnoses("상품 A");
        UUID productA = diagnoses.getProducts().getFirst().getId();

        // when
        List<String> results = runConcurrently(
                () -> productService.removeProduct(USER_ID, productA),
                () -> productService.removeProduct(USER_ID, productA));

        // then
        assertThat(results).containsExactlyInAnyOrder(SUCCESS, CommonResponseCode.NOT_FOUND.getCode());
        assertThat(productRepository.count()).isZero();
        assertThat(diagnosesRepository.count()).isZero();
    }

    private Diagnoses saveDiagnoses(String... productNames) {
        Diagnoses diagnoses = Diagnoses.pending(USER_ID);
        diagnoses.addProducts(List.of(productNames).stream()
                .map(name -> Product.pending(name, PRODUCT_IMAGE_KEY, SourceType.URL, SOURCE_URL, null))
                .toList());
        return diagnosesRepository.save(diagnoses);
    }

    // 두 작업을 동시에 출발시키고, 각 결과를 SUCCESS 또는 BaseException 의 응답 코드로 돌려준다.
    // BaseException 이 아닌 예외(예: 낙관적 락 실패로 인한 500)는 그대로 테스트를 실패시킨다.
    private List<String> runConcurrently(Runnable... tasks) throws Exception {
        ExecutorService executor = Executors.newFixedThreadPool(tasks.length);
        CountDownLatch ready = new CountDownLatch(tasks.length);
        CountDownLatch start = new CountDownLatch(1);
        try {
            List<Future<String>> futures = new ArrayList<>();
            for (Runnable task : tasks) {
                Callable<String> callable = () -> {
                    ready.countDown();
                    start.await();
                    try {
                        task.run();
                        return SUCCESS;
                    } catch (BaseException e) {
                        return e.getResponseCode().getCode();
                    }
                };
                futures.add(executor.submit(callable));
            }
            ready.await();
            start.countDown();

            List<String> results = new ArrayList<>();
            for (Future<String> future : futures) {
                try {
                    results.add(future.get(10, TimeUnit.SECONDS));
                } catch (ExecutionException e) {
                    throw new AssertionError("BaseException 이 아닌 예외가 발생했다.", e.getCause());
                }
            }
            return results;
        } finally {
            executor.shutdownNow();
        }
    }
}
