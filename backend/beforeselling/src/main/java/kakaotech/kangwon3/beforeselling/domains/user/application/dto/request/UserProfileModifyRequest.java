package kakaotech.kangwon3.beforeselling.domains.user.application.dto.request;

import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

public record UserProfileModifyRequest(

        @Pattern(regexp = ".*\\S.*", message = "이름은 공백일 수 없습니다.")
        @Size(max = 20, message = "이름은 20자를 넘을 수 없습니다.")
        String name
) {
}
