package kakaotech.kangwon3.beforeselling.domains.lawamendment.application.usecase;

import kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity.ToolName;
import kakaotech.kangwon3.beforeselling.domains.lawamendment.application.dto.callback.LawChangeCallbackRequest;
import kakaotech.kangwon3.beforeselling.domains.lawamendment.application.dto.callback.PublicLawChangeDto;
import kakaotech.kangwon3.beforeselling.domains.lawamendment.application.mapper.LawAmendmentMapper;
import kakaotech.kangwon3.beforeselling.domains.lawamendment.domain.entity.LawAmendment;
import kakaotech.kangwon3.beforeselling.domains.lawamendment.domain.service.LawAmendmentService;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.List;

import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.then;

@ExtendWith(MockitoExtension.class)
class LawAmendmentCallbackUseCaseTest {

    @Mock
    private LawAmendmentService lawAmendmentService;

    @Mock
    private LawAmendmentMapper lawAmendmentMapper;

    @Test
    @DisplayName("법령 변경 콜백을 받으면 변경을 법령 변경으로 바꿔 저장을 요청한다.")
    void receiveLawChanges_thenCreateLawAmendments() {
        // given
        LawAmendmentCallbackUseCase useCase = new LawAmendmentCallbackUseCase(lawAmendmentService, lawAmendmentMapper);
        LawChangeCallbackRequest request = new LawChangeCallbackRequest(List.of(
                new PublicLawChangeDto("어린이제품 안전 특별법 시행규칙", "012345", false,
                        ToolName.CHILDREN, "291321", null, null, null, null)));
        List<LawAmendment> lawAmendments = List.of(LawAmendment.builder().build());
        given(lawAmendmentMapper.toLawAmendments(request)).willReturn(lawAmendments);
        given(lawAmendmentService.createLawAmendments(lawAmendments)).willReturn(lawAmendments);

        // when
        useCase.receiveLawChanges(request);

        // then
        then(lawAmendmentService).should().createLawAmendments(lawAmendments);
    }
}
