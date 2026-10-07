package kakaotech.kangwon3.beforeselling.global.infra.mail;

public class MailSendFailedException extends RuntimeException {

    public MailSendFailedException(String to, Throwable cause) {
        super("메일 발송에 실패했습니다. to=%s".formatted(to), cause);
    }
}
