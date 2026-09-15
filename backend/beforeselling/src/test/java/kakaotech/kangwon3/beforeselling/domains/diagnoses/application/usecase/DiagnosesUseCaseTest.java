package kakaotech.kangwon3.beforeselling.domains.diagnoses.application.usecase;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.request.DiagnosesCreateRequest;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.DiagnosesCreateResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.mapper.DiagnosesMapper;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Diagnoses;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.SourceType;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.service.DiagnosesCreateCommand;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.service.DiagnosesService;
import kakaotech.kangwon3.beforeselling.global.infra.s3.S3FileMover;
import kakaotech.kangwon3.beforeselling.global.infra.s3.S3UrlKeyCodec;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Captor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.test.util.ReflectionTestUtils;
import software.amazon.awssdk.services.s3.model.NoSuchKeyException;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.never;
import static org.mockito.BDDMockito.then;

@ExtendWith(MockitoExtension.class)
class DiagnosesUseCaseTest {

    private static final String TEMP_PRODUCT_IMAGE_KEY = "temp/product-main/1/a_thumb.jpg";
    private static final String PERMANENT_PRODUCT_IMAGE_KEY = "product-main/1/a_thumb.jpg";
    private static final String TEMP_IMAGE_KEY_1 = "temp/product-detail/1/b_1.jpg";
    private static final String PERMANENT_IMAGE_KEY_1 = "product-detail/1/b_1.jpg";

    @Mock
    private DiagnosesService diagnosesService;

    @Mock
    private S3FileMover s3FileMover;

    @Mock
    private S3UrlKeyCodec s3UrlKeyCodec;

    private DiagnosesUseCase diagnosesUseCase;

    @Captor
    private ArgumentCaptor<DiagnosesCreateCommand> commandCaptor;

    @BeforeEach
    void setUp() {
        diagnosesUseCase = new DiagnosesUseCase(diagnosesService, new DiagnosesMapper(s3UrlKeyCodec), s3FileMover);
    }

    @Test
    @DisplayName("진단서를 생성하면 temp 경로 key들을 정식 경로로 이동시킨 뒤 이동된 key로 진단서를 저장한다.")
    void createDiagnoses_thenMoveKeysToPermanentBeforeSaving() {
        // given
        DiagnosesCreateRequest request = new DiagnosesCreateRequest(
                "대나무 헬리콥터", TEMP_PRODUCT_IMAGE_KEY, SourceType.URL,
                "https://ko.aliexpress.com/item/100500628491", null, List.of(TEMP_IMAGE_KEY_1));

        given(s3FileMover.moveToPermanent(TEMP_PRODUCT_IMAGE_KEY)).willReturn(PERMANENT_PRODUCT_IMAGE_KEY);
        given(s3FileMover.moveAllToPermanent(List.of(TEMP_IMAGE_KEY_1))).willReturn(List.of(PERMANENT_IMAGE_KEY_1));

        Diagnoses saved = Diagnoses.pending(1L, "대나무 헬리콥터", PERMANENT_PRODUCT_IMAGE_KEY,
                SourceType.URL, "https://ko.aliexpress.com/item/100500628491", null);
        ReflectionTestUtils.setField(saved, "id", 10L);
        given(diagnosesService.createDiagnoses(any(DiagnosesCreateCommand.class))).willReturn(saved);

        // when
        DiagnosesCreateResponse response = diagnosesUseCase.createDiagnoses(1L, request);

        // then
        assertThat(response.diagnosesId()).isEqualTo(10L);

        then(diagnosesService).should().createDiagnoses(commandCaptor.capture());
        DiagnosesCreateCommand command = commandCaptor.getValue();
        assertThat(command.productImageKey()).isEqualTo(PERMANENT_PRODUCT_IMAGE_KEY);
        assertThat(command.imageKeys()).containsExactly(PERMANENT_IMAGE_KEY_1);
    }

    @Test
    @DisplayName("key 이동이 실패하면 진단서 생성 자체를 호출하지 않는다.")
    void createDiagnoses_withMoveFailure_thenDoesNotCallDiagnosesService() {
        // given
        DiagnosesCreateRequest request = new DiagnosesCreateRequest(
                "대나무 헬리콥터", TEMP_PRODUCT_IMAGE_KEY, SourceType.URL,
                "https://ko.aliexpress.com/item/100500628491", null, List.of());

        given(s3FileMover.moveToPermanent(TEMP_PRODUCT_IMAGE_KEY))
                .willThrow(NoSuchKeyException.builder().message("no such key").build());

        // when & then
        assertThatThrownBy(() -> diagnosesUseCase.createDiagnoses(1L, request))
                .isInstanceOf(NoSuchKeyException.class);

        then(diagnosesService).should(never()).createDiagnoses(any());
    }
}
