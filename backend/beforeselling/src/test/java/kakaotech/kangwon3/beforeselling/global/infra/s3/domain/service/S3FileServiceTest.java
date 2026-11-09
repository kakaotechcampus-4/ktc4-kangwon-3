package kakaotech.kangwon3.beforeselling.global.infra.s3.domain.service;

import kakaotech.kangwon3.beforeselling.global.common.CommonResponseCode;
import kakaotech.kangwon3.beforeselling.global.exception.BaseException;
import kakaotech.kangwon3.beforeselling.global.infra.s3.FileType;
import kakaotech.kangwon3.beforeselling.global.infra.s3.domain.entity.S3File;
import kakaotech.kangwon3.beforeselling.global.infra.s3.domain.entity.S3FileStatus;
import kakaotech.kangwon3.beforeselling.global.infra.s3.domain.repository.S3FileRepository;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Captor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.data.domain.PageRequest;
import org.springframework.test.util.ReflectionTestUtils;

import java.time.LocalDateTime;
import java.util.List;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatCode;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyList;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.then;

@ExtendWith(MockitoExtension.class)
class S3FileServiceTest {

    private static final String KEY = "diagnoses/1/uuid_file.jpg";
    private static final UUID USER_ID = UUID.randomUUID();
    private static final UUID OTHER_USER_ID = UUID.randomUUID();
    private static final String DETAIL_KEY_PREFIX = "product-detail/" + USER_ID + "/";

    @Mock
    private S3FileRepository s3FileRepository;

    private S3FileService s3FileService;

    @org.junit.jupiter.api.BeforeEach
    void setUp() {
        s3FileService = new S3FileService(s3FileRepository);
    }

    @Test
    @DisplayName("presigned URL을 발급하면 해당 key가 PENDING 상태로 기록된다.")
    void markPending_thenSaveAsPending() {
        // when
        s3FileService.markPending(KEY);

        // then
        ArgumentCaptor<S3File> captor = ArgumentCaptor.forClass(S3File.class);
        then(s3FileRepository).should().save(captor.capture());
        assertThat(captor.getValue().getKey()).isEqualTo(KEY);
        assertThat(captor.getValue().getStatus()).isEqualTo(S3FileStatus.PENDING);
    }

    @Test
    @DisplayName("업로드가 실제로 사용되면 해당 key들이 CONFIRMED 상태로 전환된다.")
    void markConfirmed_thenTransitionStatus() {
        // given
        S3File pending = S3File.pending(KEY);
        given(s3FileRepository.findByKeyIn(List.of(KEY))).willReturn(List.of(pending));

        // when
        s3FileService.markConfirmed(List.of(KEY));

        // then
        assertThat(pending.getStatus()).isEqualTo(S3FileStatus.CONFIRMED);
    }

    @Test
    @DisplayName("빈 key 목록으로 CONFIRMED 전환을 요청하면 조회하지 않는다.")
    void markConfirmed_withEmptyKeys_thenSkip() {
        // when
        s3FileService.markConfirmed(List.of());

        // then
        then(s3FileRepository).should(org.mockito.BDDMockito.never()).findByKeyIn(anyList());
    }

    @Test
    @DisplayName("S3 삭제가 끝난 key들의 부기 레코드를 제거한다.")
    void removeByKeys_thenDeleteRows() {
        // when
        s3FileService.removeByKeys(List.of(KEY));

        // then
        then(s3FileRepository).should().deleteByKeyIn(List.of(KEY));
    }

    @Test
    @DisplayName("빈 key 목록으로 제거를 요청하면 삭제 쿼리를 호출하지 않는다.")
    void removeByKeys_withEmptyKeys_thenSkip() {
        // when
        s3FileService.removeByKeys(List.of());

        // then
        then(s3FileRepository).should(org.mockito.BDDMockito.never()).deleteByKeyIn(anyList());
    }

    @Test
    @DisplayName("만료 기준 이전에 생성된 PENDING 파일만 조회한다.")
    void findExpiredPending_delegatesToRepository() {
        // given
        LocalDateTime threshold = LocalDateTime.now().minusHours(24);
        PageRequest pageable = PageRequest.of(0, 500);
        given(s3FileRepository.findByStatusAndCreatedAtBefore(S3FileStatus.PENDING, threshold, pageable))
                .willReturn(List.of(S3File.pending(KEY)));

        // when
        List<S3File> result = s3FileService.findExpiredPending(threshold, pageable);

        // then
        assertThat(result).hasSize(1);
        then(s3FileRepository).should().findByStatusAndCreatedAtBefore(S3FileStatus.PENDING, threshold, pageable);
    }

    @Test
    @DisplayName("모든 key가 본인에게 발급된 해당 폴더의 key면 소유권 확인을 통과한다.")
    void validateOwner_withOwnKeys_thenPass() {
        // given
        List<String> keys = List.of(DETAIL_KEY_PREFIX + "uuid_a1.jpg", DETAIL_KEY_PREFIX + "uuid_a2.jpg");

        // when & then
        assertThatCode(() -> s3FileService.validateOwner(USER_ID, FileType.PRODUCT_DETAIL, keys))
                .doesNotThrowAnyException();
    }

    @Test
    @DisplayName("key 중 하나라도 다른 사용자에게 발급된 key면 NOT_FOUND 예외가 발생한다.")
    void validateOwner_withOtherUsersKey_thenNotFound() {
        // given
        List<String> keys = List.of(
                DETAIL_KEY_PREFIX + "uuid_a1.jpg", "product-detail/" + OTHER_USER_ID + "/uuid_b1.jpg");

        // when & then
        assertThatThrownBy(() -> s3FileService.validateOwner(USER_ID, FileType.PRODUCT_DETAIL, keys))
                .isInstanceOf(BaseException.class)
                .extracting(e -> ((BaseException) e).getResponseCode())
                .isEqualTo(CommonResponseCode.NOT_FOUND);
    }

    @Test
    @DisplayName("다른 폴더의 key면 NOT_FOUND 예외가 발생한다.")
    void validateOwner_withOtherFolderKey_thenNotFound() {
        // given
        List<String> keys = List.of(DETAIL_KEY_PREFIX + "uuid_a1.jpg");

        // when & then
        assertThatThrownBy(() -> s3FileService.validateOwner(USER_ID, FileType.PRODUCT_MAIN, keys))
                .isInstanceOf(BaseException.class)
                .extracting(e -> ((BaseException) e).getResponseCode())
                .isEqualTo(CommonResponseCode.NOT_FOUND);
    }

    @Test
    @DisplayName("확인할 key가 없으면 소유권 확인을 통과한다.")
    void validateOwner_withEmptyKeys_thenPass() {
        // when & then
        assertThatCode(() -> s3FileService.validateOwner(USER_ID, FileType.PRODUCT_DETAIL, List.of()))
                .doesNotThrowAnyException();
        assertThatCode(() -> s3FileService.validateOwner(USER_ID, FileType.PRODUCT_DETAIL, null))
                .doesNotThrowAnyException();
    }
}
