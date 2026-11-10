package kakaotech.kangwon3.beforeselling.domains.diagnoses.application.usecase;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.request.DiagnosesCreateRequest;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.dto.response.DiagnosesCreateResponse;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.application.mapper.DiagnosesMapper;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.Diagnoses;
import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.service.DiagnosesService;
import kakaotech.kangwon3.beforeselling.domains.user.domain.service.UserService;
import kakaotech.kangwon3.beforeselling.global.common.CommonResponseCode;
import kakaotech.kangwon3.beforeselling.global.exception.BaseException;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.List;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.then;
import static org.mockito.BDDMockito.willThrow;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;

@ExtendWith(MockitoExtension.class)
class DiagnosesUseCaseTest {

    private static final UUID USER_ID = UUID.randomUUID();

    @Mock
    private DiagnosesService diagnosesService;

    @Mock
    private UserService userService;

    @Mock
    private DiagnosesMapper diagnosesMapper;

    @InjectMocks
    private DiagnosesUseCase diagnosesUseCase;

    @Test
    @DisplayName("회원이 진단을 요청하면 진단서를 생성하고 생성된 진단서 ID를 돌려준다.")
    void createDiagnoses_thenReturnResponse() {
        // given
        DiagnosesCreateRequest request = new DiagnosesCreateRequest(List.of());
        Diagnoses diagnoses = mock(Diagnoses.class);
        DiagnosesCreateResponse expected = new DiagnosesCreateResponse(UUID.randomUUID());
        given(diagnosesMapper.toCommands(request)).willReturn(List.of());
        given(diagnosesService.createDiagnoses(USER_ID, List.of())).willReturn(diagnoses);
        given(diagnosesMapper.toCreateResponse(diagnoses)).willReturn(expected);

        // when
        DiagnosesCreateResponse response = diagnosesUseCase.createDiagnoses(USER_ID, request);

        // then
        assertThat(response).isSameAs(expected);
    }

    @Test
    @DisplayName("탈퇴한 회원이 진단을 요청하면 NOT_FOUND 예외가 발생하고 진단서를 생성하지 않는다.")
    void createDiagnoses_withWithdrawnUser_thenThrow() {
        // given
        willThrow(new BaseException(CommonResponseCode.NOT_FOUND)).given(userService).validateExists(USER_ID);

        // when & then
        assertThatThrownBy(() -> diagnosesUseCase.createDiagnoses(USER_ID, new DiagnosesCreateRequest(List.of())))
                .isInstanceOf(BaseException.class)
                .extracting(e -> ((BaseException) e).getResponseCode())
                .isEqualTo(CommonResponseCode.NOT_FOUND);
        then(diagnosesService).should(never()).createDiagnoses(any(), any());
    }
}
