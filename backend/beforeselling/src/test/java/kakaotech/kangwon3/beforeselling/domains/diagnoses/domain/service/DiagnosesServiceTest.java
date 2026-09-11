package kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.service;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Diagnoses;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.DiagnosesImage;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ProcessingStatus;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ResultStatus;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.SourceType;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.repository.DiagnosesImageRepository;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.repository.DiagnosesRepository;
import kakaotech.kangwon3.beforeselling.global.common.CommonResponseCode;
import kakaotech.kangwon3.beforeselling.global.exception.BaseException;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Captor;
import org.mockito.InOrder;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.test.util.ReflectionTestUtils;

import java.util.List;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.assertj.core.api.Assertions.tuple;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.never;
import static org.mockito.BDDMockito.then;
import static org.mockito.Mockito.inOrder;

@ExtendWith(MockitoExtension.class)
class DiagnosesServiceTest {

    private static final String PRODUCT_NAME = "대나무 헬리콥터";
    private static final String PRODUCT_IMAGE_URL = "https://image.com/thumbnail";
    private static final String SOURCE_URL = "https://ko.aliexpress.com/item/100500628491";

    @Mock
    private DiagnosesRepository diagnosesRepository;

    @Mock
    private DiagnosesImageRepository diagnosesImageRepository;

    @InjectMocks
    private DiagnosesService diagnosesService;

    @Captor
    private ArgumentCaptor<Diagnoses> diagnosesCaptor;

    @Captor
    private ArgumentCaptor<List<DiagnosesImage>> imagesCaptor;

    @Test
    @DisplayName("진단을 요청하면 진단서가 PENDING 상태로 저장되고 진단 결과는 비어 있다.")
    void createDiagnoses_thenSaveAsPending() {
        // given
        given(diagnosesRepository.save(any(Diagnoses.class))).willReturn(createDiagnoses(1L, 1L));

        // when
        diagnosesService.createDiagnoses(createCommand(1L, List.of()));

        // then
        then(diagnosesRepository).should().save(diagnosesCaptor.capture());
        Diagnoses saved = diagnosesCaptor.getValue();

        assertThat(saved.getProcessingStatus()).isEqualTo(ProcessingStatus.PENDING);
        assertThat(saved.getResultStatus()).isNull();
        assertThat(saved.getSummary()).isNull();
        assertThat(saved.getProductName()).isEqualTo(PRODUCT_NAME);
    }

    @Test
    @DisplayName("이미지를 여러 장 등록하면 업로드한 순서대로 정렬 값이 부여된다.")
    void createDiagnoses_withImages_thenAssignSortOrderByUploadOrder() {
        // given
        given(diagnosesRepository.save(any(Diagnoses.class))).willReturn(createDiagnoses(1L, 1L));
        List<String> imageUrls = List.of("https://image.com/1", "https://image.com/2", "https://image.com/3");

        // when
        diagnosesService.createDiagnoses(createCommand(1L, imageUrls));

        // then
        then(diagnosesImageRepository).should().saveAll(imagesCaptor.capture());

        assertThat(imagesCaptor.getValue())
                .extracting(DiagnosesImage::getImageUrl, DiagnosesImage::getSortOrder)
                .containsExactly(
                        tuple("https://image.com/1", 0),
                        tuple("https://image.com/2", 1),
                        tuple("https://image.com/3", 2));
    }

    @Test
    @DisplayName("이미지 없이 진단을 요청하면 진단서만 저장된다.")
    void createDiagnoses_withoutImages_thenSaveDiagnosesOnly() {
        // given
        given(diagnosesRepository.save(any(Diagnoses.class))).willReturn(createDiagnoses(1L, 1L));

        // when
        diagnosesService.createDiagnoses(createCommand(1L, List.of()));

        // then
        then(diagnosesImageRepository).should().saveAll(imagesCaptor.capture());
        assertThat(imagesCaptor.getValue()).isEmpty();
    }

    @Test
    @DisplayName("본인의 진단서를 조회하면 해당 진단서를 반환한다.")
    void getDiagnoses_thenReturnDiagnoses() {
        // given
        Diagnoses diagnoses = createDiagnoses(1L, 1L);
        given(diagnosesRepository.findById(1L)).willReturn(Optional.of(diagnoses));

        // when
        Diagnoses result = diagnosesService.getDiagnoses(1L, 1L);

        // then
        assertThat(result).isEqualTo(diagnoses);
    }

    @Test
    @DisplayName("존재하지 않는 진단서를 조회하면 NOT_FOUND 예외가 발생한다.")
    void getDiagnoses_withUnknownId_thenThrowNotFound() {
        // given
        given(diagnosesRepository.findById(1L)).willReturn(Optional.empty());

        // when & then
        assertThatThrownBy(() -> diagnosesService.getDiagnoses(1L, 1L))
                .isInstanceOf(BaseException.class)
                .extracting(e -> ((BaseException) e).getResponseCode())
                .isEqualTo(CommonResponseCode.NOT_FOUND);
    }

    @Test
    @DisplayName("다른 사용자의 진단서를 조회하면 FORBIDDEN 예외가 발생한다.")
    void getDiagnoses_withOtherUsersDiagnoses_thenThrowForbidden() {
        // given
        given(diagnosesRepository.findById(1L)).willReturn(Optional.of(createDiagnoses(1L, 2L)));

        // when & then
        assertThatThrownBy(() -> diagnosesService.getDiagnoses(1L, 1L))
                .isInstanceOf(BaseException.class)
                .extracting(e -> ((BaseException) e).getResponseCode())
                .isEqualTo(CommonResponseCode.FORBIDDEN);
    }

    @Test
    @DisplayName("결과 필터 없이 목록을 조회하면 사용자의 전체 진단서를 조회한다.")
    void getDiagnosesList_withoutFilter_thenFindAllOfUser() {
        // given
        Pageable pageable = PageRequest.of(0, 10);

        // when
        diagnosesService.getDiagnosesList(1L, null, pageable);

        // then
        then(diagnosesRepository).should().findByUserId(1L, pageable);
        then(diagnosesRepository).should(never()).findByUserIdAndResultStatus(any(), any(), any());
    }

    @Test
    @DisplayName("결과 필터를 지정해 목록을 조회하면 해당 결과의 진단서만 조회한다.")
    void getDiagnosesList_withFilter_thenFindByResultStatus() {
        // given
        Pageable pageable = PageRequest.of(0, 10);

        // when
        diagnosesService.getDiagnosesList(1L, ResultStatus.RECHECK_REQUIRED, pageable);

        // then
        then(diagnosesRepository).should()
                .findByUserIdAndResultStatus(1L, ResultStatus.RECHECK_REQUIRED, pageable);
        then(diagnosesRepository).should(never()).findByUserId(any(), any());
    }

    @Test
    @DisplayName("진단서를 삭제하면 딸린 이미지가 먼저 삭제된 뒤 진단서가 삭제된다.")
    void removeDiagnoses_thenDeleteImagesBeforeDiagnoses() {
        // given
        Diagnoses diagnoses = createDiagnoses(1L, 1L);
        given(diagnosesRepository.findById(1L)).willReturn(Optional.of(diagnoses));

        // when
        diagnosesService.removeDiagnoses(1L, 1L);

        // then
        InOrder inOrder = inOrder(diagnosesImageRepository, diagnosesRepository);
        inOrder.verify(diagnosesImageRepository).deleteByDiagnosesId(1L);
        inOrder.verify(diagnosesRepository).delete(diagnoses);
    }

    @Test
    @DisplayName("다른 사용자의 진단서를 삭제하면 FORBIDDEN 예외가 발생하고 아무것도 삭제되지 않는다.")
    void removeDiagnoses_withOtherUsersDiagnoses_thenThrowForbidden() {
        // given
        given(diagnosesRepository.findById(1L)).willReturn(Optional.of(createDiagnoses(1L, 2L)));

        // when & then
        assertThatThrownBy(() -> diagnosesService.removeDiagnoses(1L, 1L))
                .isInstanceOf(BaseException.class)
                .extracting(e -> ((BaseException) e).getResponseCode())
                .isEqualTo(CommonResponseCode.FORBIDDEN);

        then(diagnosesImageRepository).should(never()).deleteByDiagnosesId(any());
        then(diagnosesRepository).should(never()).delete(any());
    }

    private Diagnoses createDiagnoses(Long diagnosesId, Long userId) {
        Diagnoses diagnoses = Diagnoses.pending(
                userId, PRODUCT_NAME, PRODUCT_IMAGE_URL, SourceType.URL, SOURCE_URL, null);
        ReflectionTestUtils.setField(diagnoses, "id", diagnosesId);
        return diagnoses;
    }

    private DiagnosesCreateCommand createCommand(Long userId, List<String> imageUrls) {
        return new DiagnosesCreateCommand(
                userId, PRODUCT_NAME, PRODUCT_IMAGE_URL, SourceType.URL, SOURCE_URL, null, imageUrls);
    }
}
