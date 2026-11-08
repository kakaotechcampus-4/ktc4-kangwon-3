package kakaotech.kangwon3.beforeselling.global.infra.s3;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;

class FileTypeTest {

    private static final UUID USER_ID = UUID.randomUUID();
    private static final UUID OTHER_USER_ID = UUID.randomUUID();

    @Test
    @DisplayName("key 접두어는 폴더명과 사용자 ID로 만든다.")
    void keyPrefix_thenReturnFolderAndUserId() {
        // when
        String prefix = FileType.PRODUCT_MAIN.keyPrefix(USER_ID);

        // then
        assertThat(prefix).isEqualTo("product-main/" + USER_ID + "/");
    }

    @Test
    @DisplayName("본인에게 발급된 key면 소유자로 판단한다.")
    void isOwnedBy_withOwnKey_thenTrue() {
        // given
        String key = "product-detail/" + USER_ID + "/uuid_a1.jpg";

        // when & then
        assertThat(FileType.PRODUCT_DETAIL.isOwnedBy(key, USER_ID)).isTrue();
    }

    @Test
    @DisplayName("다른 사용자에게 발급된 key면 소유자가 아니다.")
    void isOwnedBy_withOtherUsersKey_thenFalse() {
        // given
        String key = "product-detail/" + OTHER_USER_ID + "/uuid_a1.jpg";

        // when & then
        assertThat(FileType.PRODUCT_DETAIL.isOwnedBy(key, USER_ID)).isFalse();
    }

    @Test
    @DisplayName("다른 폴더의 key면 소유자가 아니다.")
    void isOwnedBy_withOtherFolderKey_thenFalse() {
        // given
        String key = "product-main/" + USER_ID + "/uuid_a1.jpg";

        // when & then
        assertThat(FileType.PRODUCT_DETAIL.isOwnedBy(key, USER_ID)).isFalse();
    }

    @Test
    @DisplayName("접두어 뒤에 경로가 더 붙은 key면 소유자가 아니다.")
    void isOwnedBy_withNestedPath_thenFalse() {
        // given
        String key = "product-detail/" + USER_ID + "/../" + OTHER_USER_ID + "/uuid_a1.jpg";

        // when & then
        assertThat(FileType.PRODUCT_DETAIL.isOwnedBy(key, USER_ID)).isFalse();
    }

    @Test
    @DisplayName("파일명 없이 접두어만 있는 key면 소유자가 아니다.")
    void isOwnedBy_withPrefixOnly_thenFalse() {
        // given
        String key = FileType.PRODUCT_DETAIL.keyPrefix(USER_ID);

        // when & then
        assertThat(FileType.PRODUCT_DETAIL.isOwnedBy(key, USER_ID)).isFalse();
    }

    @Test
    @DisplayName("key가 없으면 소유자가 아니다.")
    void isOwnedBy_withNull_thenFalse() {
        // when & then
        assertThat(FileType.PRODUCT_DETAIL.isOwnedBy(null, USER_ID)).isFalse();
    }
}
