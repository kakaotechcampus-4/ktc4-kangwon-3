package kakaotech.kangwon3.beforeselling.global.controller;

import kakaotech.kangwon3.beforeselling.global.common.CommonResponseCode;
import kakaotech.kangwon3.beforeselling.global.controller.ErrorCodeController.ErrorCodeGroup;
import kakaotech.kangwon3.beforeselling.global.controller.ErrorCodeController.ErrorCodeInfo;
import kakaotech.kangwon3.beforeselling.global.infra.s3.FileResponseCode;
import kakaotech.kangwon3.beforeselling.global.security.constant.AuthResponseCode;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.ui.ExtendedModelMap;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class ErrorCodeControllerTest {

    private final ErrorCodeController controller = new ErrorCodeController();

    @Test
    @DisplayName("에러 코드 페이지는 공통·인증·파일 응답 코드를 그룹별로 모두 담는다.")
    void showErrorCodes_thenGroupAllResponseCodes() {
        // given
        ExtendedModelMap model = new ExtendedModelMap();

        // when
        String view = controller.showErrorCodes(model);

        // then
        assertThat(view).isEqualTo("error-codes");
        @SuppressWarnings("unchecked")
        List<ErrorCodeGroup> groups = (List<ErrorCodeGroup>) model.get("groups");
        assertThat(groups).extracting(ErrorCodeGroup::name).containsExactly("공통", "인증", "파일");
        assertThat(groups.get(0).codes()).hasSize(CommonResponseCode.values().length);
        assertThat(groups.get(1).codes()).hasSize(AuthResponseCode.values().length);
        assertThat(groups.get(2).codes()).hasSize(FileResponseCode.values().length);
    }

    @Test
    @DisplayName("각 코드에는 enum 이름, HTTP 상태, 서비스 코드, 메시지가 담긴다.")
    void showErrorCodes_thenCodeInfoHasAllFields() {
        // given
        ExtendedModelMap model = new ExtendedModelMap();

        // when
        controller.showErrorCodes(model);

        // then
        @SuppressWarnings("unchecked")
        List<ErrorCodeGroup> groups = (List<ErrorCodeGroup>) model.get("groups");
        CommonResponseCode notFound = CommonResponseCode.NOT_FOUND;
        assertThat(groups.get(0).codes()).contains(new ErrorCodeInfo(
                notFound.name(),
                notFound.getStatus().value(),
                notFound.getStatus().getReasonPhrase(),
                notFound.getCode(),
                notFound.getMessage()));
    }
}
