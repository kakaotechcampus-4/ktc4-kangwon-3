package kakaotech.kangwon3.beforeselling.global.infra.mail;

public record MailMessage(
        String to,
        String subject,
        String htmlBody
) {
}
