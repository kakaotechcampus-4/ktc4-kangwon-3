package kakaotech.kangwon3.beforeselling.global.security.crypto;

import kakaotech.kangwon3.beforeselling.global.config.properties.CryptoProperties;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class DatabaseEncryptionConverterTest {

    private static final String SECRET_KEY = "f2Oy84aaJTR8qL/qOjUYcpjozTbFaqlUD57FrxpHLM8=";

    private DatabaseEncryptionConverter converter;

    @BeforeEach
    void setUp() {
        converter = new DatabaseEncryptionConverter(new CryptoProperties(SECRET_KEY));
        converter.init();
    }

    @Test
    @DisplayName("암호화 후 복호화하면 원문이 그대로 복원된다.")
    void encryptAndDecrypt_thenRestoreOriginal() {
        // given
        String plainText = "naver-refresh-token-value";

        // when
        String encrypted = converter.convertToDatabaseColumn(plainText);
        String decrypted = converter.convertToEntityAttribute(encrypted);

        // then
        assertThat(decrypted).isEqualTo(plainText);
    }

    @Test
    @DisplayName("같은 평문이어도 호출마다 IV가 달라 암호문이 매번 다르다.")
    void encrypt_withSamePlainText_thenProducesDifferentCipherText() {
        // given
        String plainText = "google-refresh-token-value";

        // when
        String encrypted1 = converter.convertToDatabaseColumn(plainText);
        String encrypted2 = converter.convertToDatabaseColumn(plainText);

        // then
        assertThat(encrypted1).isNotEqualTo(encrypted2);
    }

    @Test
    @DisplayName("null을 암호화하면 null을 반환하고, null을 복호화해도 null을 반환한다.")
    void convert_withNull_thenReturnNull() {
        assertThat(converter.convertToDatabaseColumn(null)).isNull();
        assertThat(converter.convertToEntityAttribute(null)).isNull();
    }

    @Test
    @DisplayName("Base64 형식이 아닌 데이터를 복호화하면 IllegalStateException을 던진다.")
    void convertToEntityAttribute_withInvalidBase64_thenThrow() {
        assertThatThrownBy(() -> converter.convertToEntityAttribute("not-a-valid-base64!!"))
                .isInstanceOf(IllegalStateException.class);
    }
}
