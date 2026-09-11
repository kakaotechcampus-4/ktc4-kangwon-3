package kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.repository;

import jakarta.persistence.EntityManager;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Diagnoses;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.DiagnosesImage;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ResultStatus;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.SourceType;
import kakaotech.kangwon3.beforeselling.global.config.JpaAuditingConfig;
import kakaotech.kangwon3.beforeselling.global.config.properties.CryptoProperties;
import kakaotech.kangwon3.beforeselling.global.security.crypto.DatabaseEncryptionConverter;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.boot.data.jpa.test.autoconfigure.DataJpaTest;
import org.springframework.boot.jdbc.test.autoconfigure.AutoConfigureTestDatabase;
import org.springframework.context.annotation.Import;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Sort;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.util.ReflectionTestUtils;

import java.util.Comparator;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

@DataJpaTest
@ActiveProfiles("test")
@AutoConfigureTestDatabase(replace = AutoConfigureTestDatabase.Replace.NONE)
@Import({JpaAuditingConfig.class, DatabaseEncryptionConverter.class})
@EnableConfigurationProperties(CryptoProperties.class)
class DiagnosesRepositoryTest {

    private static final Long USER_ID = 1L;
    private static final Long OTHER_USER_ID = 2L;

    @Autowired
    private DiagnosesRepository diagnosesRepository;

    @Autowired
    private DiagnosesImageRepository diagnosesImageRepository;

    @Autowired
    private EntityManager entityManager;

    @Test
    @DisplayName("진단서를 저장하면 등록 시각이 자동으로 기록된다.")
    void save_thenRecordCreatedAt() {
        // given & when
        Diagnoses saved = diagnosesRepository.save(createDiagnoses(USER_ID, null));

        // then
        assertThat(saved.getCreatedAt()).isNotNull();
        assertThat(saved.getUpdatedAt()).isNotNull();
    }

    @Test
    @DisplayName("진단서의 이미지를 조회하면 업로드한 순서대로 반환된다.")
    void findByDiagnosesIdOrderBySortOrderAsc_thenReturnInUploadOrder() {
        // given
        Diagnoses diagnoses = diagnosesRepository.save(createDiagnoses(USER_ID, null));
        Long diagnosesId = diagnoses.getId();

        // 저장 순서를 일부러 뒤섞는다.
        diagnosesImageRepository.save(DiagnosesImage.of(diagnosesId, "https://image.com/3", 2));
        diagnosesImageRepository.save(DiagnosesImage.of(diagnosesId, "https://image.com/1", 0));
        diagnosesImageRepository.save(DiagnosesImage.of(diagnosesId, "https://image.com/2", 1));
        flushAndClear();

        // when
        List<DiagnosesImage> result = diagnosesImageRepository.findByDiagnosesIdOrderBySortOrderAsc(diagnosesId);

        // then
        assertThat(result)
                .extracting(DiagnosesImage::getImageUrl)
                .containsExactly("https://image.com/1", "https://image.com/2", "https://image.com/3");
    }

    @Test
    @DisplayName("진단서의 이미지를 삭제하면 해당 진단서의 이미지만 제거된다.")
    void deleteByDiagnosesId_thenDeleteOnlyItsImages() {
        // given
        Diagnoses target = diagnosesRepository.save(createDiagnoses(USER_ID, null));
        Diagnoses other = diagnosesRepository.save(createDiagnoses(USER_ID, null));

        diagnosesImageRepository.save(DiagnosesImage.of(target.getId(), "https://image.com/1", 0));
        diagnosesImageRepository.save(DiagnosesImage.of(target.getId(), "https://image.com/2", 1));
        diagnosesImageRepository.save(DiagnosesImage.of(other.getId(), "https://image.com/9", 0));
        flushAndClear();

        // when
        diagnosesImageRepository.deleteByDiagnosesId(target.getId());
        flushAndClear();

        // then
        assertThat(diagnosesImageRepository.findByDiagnosesIdOrderBySortOrderAsc(target.getId())).isEmpty();
        assertThat(diagnosesImageRepository.findByDiagnosesIdOrderBySortOrderAsc(other.getId())).hasSize(1);
    }

    @Test
    @DisplayName("마이페이지 목록을 조회하면 다른 사용자의 진단서는 제외된다.")
    void findByUserId_thenExcludeOtherUsersDiagnoses() {
        // given
        diagnosesRepository.save(createDiagnoses(USER_ID, null));
        diagnosesRepository.save(createDiagnoses(USER_ID, null));
        diagnosesRepository.save(createDiagnoses(OTHER_USER_ID, null));
        flushAndClear();

        // when
        Page<Diagnoses> result = diagnosesRepository.findByUserId(USER_ID, PageRequest.of(0, 10));

        // then
        assertThat(result.getTotalElements()).isEqualTo(2);
        assertThat(result.getContent())
                .extracting(Diagnoses::getUserId)
                .containsOnly(USER_ID);
    }

    @Test
    @DisplayName("목록을 최신순으로 조회하면 등록 시각 내림차순으로 반환된다.")
    void findByUserId_withLatestSort_thenSortByCreatedAtDescending() {
        // given
        diagnosesRepository.save(createDiagnoses(USER_ID, null));
        diagnosesRepository.save(createDiagnoses(USER_ID, null));
        diagnosesRepository.save(createDiagnoses(USER_ID, null));
        flushAndClear();

        PageRequest pageRequest = PageRequest.of(0, 10, Sort.by(Sort.Direction.DESC, "createdAt"));

        // when
        Page<Diagnoses> result = diagnosesRepository.findByUserId(USER_ID, pageRequest);

        // then
        assertThat(result.getContent())
                .hasSize(3)
                .isSortedAccordingTo(Comparator.comparing(Diagnoses::getCreatedAt).reversed());
    }

    @Test
    @DisplayName("페이지 크기보다 진단서가 많으면 다음 페이지가 있다고 응답한다.")
    void findByUserId_withSmallPageSize_thenHasNext() {
        // given
        diagnosesRepository.save(createDiagnoses(USER_ID, null));
        diagnosesRepository.save(createDiagnoses(USER_ID, null));
        diagnosesRepository.save(createDiagnoses(USER_ID, null));
        flushAndClear();

        // when
        Page<Diagnoses> result = diagnosesRepository.findByUserId(USER_ID, PageRequest.of(0, 2));

        // then
        assertThat(result.getContent()).hasSize(2);
        assertThat(result.getTotalElements()).isEqualTo(3);
        assertThat(result.getTotalPages()).isEqualTo(2);
        assertThat(result.hasNext()).isTrue();
    }

    @Test
    @DisplayName("결과 필터로 목록을 조회하면 해당 결과의 진단서만 반환된다.")
    void findByUserIdAndResultStatus_thenReturnMatchingOnly() {
        // given
        diagnosesRepository.save(createDiagnoses(USER_ID, ResultStatus.RECHECK_REQUIRED));
        diagnosesRepository.save(createDiagnoses(USER_ID, ResultStatus.PURCHASING_AGENT_ALLOWED));
        flushAndClear();

        // when
        Page<Diagnoses> result = diagnosesRepository.findByUserIdAndResultStatus(
                USER_ID, ResultStatus.RECHECK_REQUIRED, PageRequest.of(0, 10));

        // then
        assertThat(result.getTotalElements()).isEqualTo(1);
        assertThat(result.getContent().getFirst().getResultStatus())
                .isEqualTo(ResultStatus.RECHECK_REQUIRED);
    }

    @Test
    @DisplayName("결과 필터로 목록을 조회하면 진단이 완료되지 않은 진단서는 조회되지 않는다.")
    void findByUserIdAndResultStatus_thenExcludePendingDiagnoses() {
        // given
        diagnosesRepository.save(createDiagnoses(USER_ID, null));
        diagnosesRepository.save(createDiagnoses(USER_ID, ResultStatus.RECHECK_REQUIRED));
        flushAndClear();

        // when
        Page<Diagnoses> result = diagnosesRepository.findByUserIdAndResultStatus(
                USER_ID, ResultStatus.RECHECK_REQUIRED, PageRequest.of(0, 10));

        // then
        assertThat(result.getTotalElements()).isEqualTo(1);
    }

    private Diagnoses createDiagnoses(Long userId, ResultStatus resultStatus) {
        Diagnoses diagnoses = Diagnoses.pending(
                userId,
                "대나무 헬리콥터",
                "https://image.com/thumbnail",
                SourceType.URL,
                "https://ko.aliexpress.com/item/100500628491",
                null);

        if (resultStatus != null) {
            ReflectionTestUtils.setField(diagnoses, "resultStatus", resultStatus);
        }
        return diagnoses;
    }

    private void flushAndClear() {
        entityManager.flush();
        entityManager.clear();
    }
}
