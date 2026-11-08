package kakaotech.kangwon3.beforeselling.domains.lawamendment.application.usecase;

import kakaotech.kangwon3.beforeselling.domains.lawamendment.application.dto.response.LawAmendmentListResponse;
import kakaotech.kangwon3.beforeselling.domains.lawamendment.application.mapper.LawAmendmentMapper;
import kakaotech.kangwon3.beforeselling.domains.lawamendment.domain.entity.LawAmendmentProduct;
import kakaotech.kangwon3.beforeselling.domains.lawamendment.domain.service.LawAmendmentService;
import kakaotech.kangwon3.beforeselling.domains.user.domain.entity.SocialProvider;
import kakaotech.kangwon3.beforeselling.domains.user.domain.entity.User;
import kakaotech.kangwon3.beforeselling.domains.user.domain.service.UserService;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.List;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.BDDMockito.given;
import static org.mockito.BDDMockito.never;
import static org.mockito.BDDMockito.then;

@ExtendWith(MockitoExtension.class)
class LawAmendmentUseCaseTest {

    private static final UUID USER_ID = UUID.randomUUID();

    @Mock
    private LawAmendmentService lawAmendmentService;

    @Mock
    private UserService userService;

    @Mock
    private LawAmendmentMapper lawAmendmentMapper;

    @InjectMocks
    private LawAmendmentUseCase lawAmendmentUseCase;

    @Test
    @DisplayName("개정 알림을 받는 회원이 조회하면 재확인 대상 상품을 개정별로 묶어 돌려준다.")
    void getLawAmendments_whenAlertEnabled_thenReturnRecheckProducts() {
        // given
        List<LawAmendmentProduct> recheckProducts = List.of();
        LawAmendmentListResponse expected = new LawAmendmentListResponse(List.of());
        given(userService.getUser(USER_ID)).willReturn(createUser());
        given(lawAmendmentService.getRecheckProducts(USER_ID)).willReturn(recheckProducts);
        given(lawAmendmentMapper.toListResponse(recheckProducts)).willReturn(expected);

        // when
        LawAmendmentListResponse response = lawAmendmentUseCase.getLawAmendments(USER_ID);

        // then
        assertThat(response).isSameAs(expected);
    }

    @Test
    @DisplayName("개정 알림을 끈 회원이 조회하면 빈 목록을 돌려주고 재확인 대상을 조회하지 않는다.")
    void getLawAmendments_whenAlertDisabled_thenEmpty() {
        // given
        User user = createUser();
        user.updateLawAmendmentAlertEnabled(false);
        given(userService.getUser(USER_ID)).willReturn(user);

        // when
        LawAmendmentListResponse response = lawAmendmentUseCase.getLawAmendments(USER_ID);

        // then
        assertThat(response.lawAmendments()).isEmpty();
        then(lawAmendmentService).should(never()).getRecheckProducts(any());
    }

    private User createUser() {
        return User.socialSignup(SocialProvider.KAKAO, "social-id", "user@example.com", "홍길동");
    }
}
