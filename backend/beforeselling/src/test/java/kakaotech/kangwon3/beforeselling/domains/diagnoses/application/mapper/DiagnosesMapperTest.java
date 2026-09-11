package kakaotech.kangwon3.beforeselling.domains.diagnoses.application.mapper;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.request.DiagnosesCreateRequest;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.DiagnosesDetailResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.DiagnosesListResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.DiagnosesSummaryResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Diagnoses;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.DiagnosesImage;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ProcessingStatus;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.SourceType;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.service.DiagnosesCreateCommand;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageImpl;
import org.springframework.data.domain.PageRequest;
import org.springframework.test.util.ReflectionTestUtils;

import java.time.LocalDateTime;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class DiagnosesMapperTest {

    private static final Long USER_ID = 1L;
    private static final String PRODUCT_NAME = "대나무 헬리콥터";
    private static final String PRODUCT_IMAGE_URL = "https://image.com/thumbnail";
    private static final String SOURCE_URL = "https://ko.aliexpress.com/item/100500628491";

    private final DiagnosesMapper diagnosesMapper = new DiagnosesMapper();

    @Test
    @DisplayName("진단 요청을 변환하면 로그인 사용자 정보가 함께 담긴다.")
    void toCommand_thenIncludeUserId() {
        // given
        DiagnosesCreateRequest request = new DiagnosesCreateRequest(
                PRODUCT_NAME, PRODUCT_IMAGE_URL, SourceType.URL, SOURCE_URL, null,
                List.of("https://image.com/1"));

        // when
        DiagnosesCreateCommand command = diagnosesMapper.toCommand(USER_ID, request);

        // then
        assertThat(command.userId()).isEqualTo(USER_ID);
        assertThat(command.productName()).isEqualTo(PRODUCT_NAME);
        assertThat(command.sourceType()).isEqualTo(SourceType.URL);
        assertThat(command.sourceUrl()).isEqualTo(SOURCE_URL);
        assertThat(command.imageUrls()).containsExactly("https://image.com/1");
    }

    @Test
    @DisplayName("이미지 없이 진단을 요청하면 이미지 목록이 빈 값으로 변환된다.")
    void toCommand_withoutImageUrls_thenReturnEmptyList() {
        // given
        DiagnosesCreateRequest request = new DiagnosesCreateRequest(
                PRODUCT_NAME, null, SourceType.URL, SOURCE_URL, null, null);

        // when
        DiagnosesCreateCommand command = diagnosesMapper.toCommand(USER_ID, request);

        // then
        assertThat(command.imageUrls()).isNotNull().isEmpty();
    }

    @Test
    @DisplayName("진단서 상세로 변환하면 이미지가 URL 목록으로 펼쳐진다.")
    void toDetailResponse_thenFlattenImagesToUrls() {
        // given
        Diagnoses diagnoses = createDiagnoses(1L);
        List<DiagnosesImage> images = List.of(
                DiagnosesImage.of(1L, "https://image.com/1", 0),
                DiagnosesImage.of(1L, "https://image.com/2", 1));

        // when
        DiagnosesDetailResponse response = diagnosesMapper.toDetailResponse(diagnoses, images);

        // then
        assertThat(response.diagnosesId()).isEqualTo(1L);
        assertThat(response.productName()).isEqualTo(PRODUCT_NAME);
        assertThat(response.imageUrls())
                .containsExactly("https://image.com/1", "https://image.com/2");
    }

    @Test
    @DisplayName("진단이 완료되지 않은 진단서를 변환하면 진단 결과가 비어 있다.")
    void toDetailResponse_withPendingDiagnoses_thenResultIsEmpty() {
        // given & when
        DiagnosesDetailResponse response = diagnosesMapper.toDetailResponse(createDiagnoses(1L), List.of());

        // then
        assertThat(response.processingStatus()).isEqualTo(ProcessingStatus.PENDING);
        assertThat(response.resultStatus()).isNull();
        assertThat(response.summary()).isNull();
        assertThat(response.imageUrls()).isEmpty();
    }

    @Test
    @DisplayName("목록 카드로 변환하면 썸네일과 상태 값만 담긴다.")
    void toSummaryResponse_thenIncludeThumbnailAndStatus() {
        // given & when
        DiagnosesSummaryResponse response = diagnosesMapper.toSummaryResponse(createDiagnoses(1L));

        // then
        assertThat(response.diagnosesId()).isEqualTo(1L);
        assertThat(response.productName()).isEqualTo(PRODUCT_NAME);
        assertThat(response.productImageUrl()).isEqualTo(PRODUCT_IMAGE_URL);
        assertThat(response.processingStatus()).isEqualTo(ProcessingStatus.PENDING);
        assertThat(response.resultStatus()).isNull();
    }

    @Test
    @DisplayName("목록으로 변환하면 진단서 요약과 페이징 정보가 함께 담긴다.")
    void toListResponse_thenIncludeSummariesAndPageInfo() {
        // given
        Page<Diagnoses> page = new PageImpl<>(
                List.of(createDiagnoses(1L), createDiagnoses(2L)),
                PageRequest.of(0, 2),
                5);

        // when
        DiagnosesListResponse response = diagnosesMapper.toListResponse(page);

        // then
        assertThat(response.diagnoses())
                .extracting(DiagnosesSummaryResponse::diagnosesId)
                .containsExactly(1L, 2L);

        DiagnosesListResponse.PageInfo pageInfo = response.pageInfo();
        assertThat(pageInfo.page()).isZero();
        assertThat(pageInfo.size()).isEqualTo(2);
        assertThat(pageInfo.totalElements()).isEqualTo(5);
        assertThat(pageInfo.totalPages()).isEqualTo(3);
        assertThat(pageInfo.hasNext()).isTrue();
    }

    private Diagnoses createDiagnoses(Long diagnosesId) {
        Diagnoses diagnoses = Diagnoses.pending(
                USER_ID, PRODUCT_NAME, PRODUCT_IMAGE_URL, SourceType.URL, SOURCE_URL, null);

        ReflectionTestUtils.setField(diagnoses, "id", diagnosesId);
        ReflectionTestUtils.setField(diagnoses, "createdAt", LocalDateTime.now());
        ReflectionTestUtils.setField(diagnoses, "updatedAt", LocalDateTime.now());
        return diagnoses;
    }
}
