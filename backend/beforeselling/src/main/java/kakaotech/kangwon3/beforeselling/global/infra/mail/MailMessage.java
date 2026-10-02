package kakaotech.kangwon3.beforeselling.global.infra.mail;

/**
 * 한 통의 메일. 발신자는 MailProperties 에서 채우므로 여기 두지 않는다
 * (호출부마다 넘기게 하면 언젠가 한 곳만 값이 달라진다).
 *
 * htmlBody 와 textBody 를 함께 보내면 multipart/alternative 로 전송되어
 * 클라이언트가 지원하는 쪽을 고른다. 텍스트 파트가 없으면 스팸 점수가 올라가고
 * 텍스트 전용 환경에서 내용을 읽을 수 없다.
 */
public record MailMessage(
        String to,
        String subject,
        String htmlBody,
        String textBody
) {
}
