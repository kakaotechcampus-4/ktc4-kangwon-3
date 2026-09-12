package kakaotech.kangwon3.beforeselling.global.controller;

import kakaotech.kangwon3.beforeselling.global.common.BaseResponseCode;
import kakaotech.kangwon3.beforeselling.global.common.CommonResponseCode;
import kakaotech.kangwon3.beforeselling.global.security.constant.AuthResponseCode;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.GetMapping;

import java.util.Arrays;
import java.util.List;

/**
 * 도메인별 응답 코드를 한 화면에 모아 보여주는 에러 코드 명세 페이지.
 * 새 도메인 ResponseCode enum을 추가하면 이 목록에도 함께 등록해야 한다.
 */
@Controller
public class ErrorCodeController {

    @GetMapping("/error-codes")
    public String showErrorCodes(Model model) {
        List<ErrorCodeGroup> groups = List.of(
                buildGroup("공통", CommonResponseCode.values()),
                buildGroup("인증", AuthResponseCode.values())
        );

        model.addAttribute("groups", groups);
        return "error-codes";
    }

    private <T extends Enum<T> & BaseResponseCode> ErrorCodeGroup buildGroup(String name, T[] values) {
        List<ErrorCodeInfo> codes = Arrays.stream(values)
                .map(v -> new ErrorCodeInfo(
                        v.name(),
                        v.getStatus().value(),
                        v.getStatus().getReasonPhrase(),
                        v.getCode(),
                        v.getMessage()
                ))
                .toList();
        return new ErrorCodeGroup(name, codes);
    }

    public record ErrorCodeGroup(String name, List<ErrorCodeInfo> codes) {
    }

    public record ErrorCodeInfo(
            String enumName,
            int httpStatusCode,
            String httpStatusReasonPhrase,
            String code,
            String message
    ) {
    }
}
