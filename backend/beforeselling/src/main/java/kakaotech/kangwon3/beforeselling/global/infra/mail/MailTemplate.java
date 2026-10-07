package kakaotech.kangwon3.beforeselling.global.infra.mail;

import lombok.Getter;
import lombok.RequiredArgsConstructor;

@Getter
@RequiredArgsConstructor
public enum MailTemplate {

    LAW_AMENDMENT("law-amendment", "[팔기전에] 관련 법령이 개정되었습니다"),
    ;

    private final String fileName;
    private final String subject;
}
