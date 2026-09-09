package kakaotech.kangwon3.beforeselling.domains.user.domain.entity;

import jakarta.persistence.*;
import kakaotech.kangwon3.beforeselling.global.common.BaseEntity;
import kakaotech.kangwon3.beforeselling.global.security.crypto.DatabaseEncryptionConverter;
import lombok.AccessLevel;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Entity
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@Table(
        name = "users",
        uniqueConstraints = @UniqueConstraint(name = "uk_users_social", columnNames = {"social_provider", "social_id"})
)
public class User extends BaseEntity {

    private static final String DEFAULT_NAME = "사용자";

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "user_id")
    private Long id;

    @Column(name = "email")
    private String email;

    @Column(name = "name", nullable = false)
    private String name;

    @Column(name = "social_id", nullable = false)
    private String socialId;

    @Enumerated(EnumType.STRING)
    @Column(name = "social_provider", nullable = false)
    private SocialProvider socialProvider;

    @Enumerated(EnumType.STRING)
    @Column(name = "role", nullable = false)
    private Role role;

    /** 소셜 제공자의 refresh_token(암호화 저장). 카카오는 사용하지 않고, 네이버/구글의 연동 해제(unlink)에 사용된다. */
    @Convert(converter = DatabaseEncryptionConverter.class)
    @Column(name = "social_refresh_token", columnDefinition = "TEXT")
    private String socialRefreshToken;

    @Builder(access = AccessLevel.PRIVATE)
    private User(String email, String name, String socialId, SocialProvider socialProvider, Role role) {
        this.email = email;
        this.name = name;
        this.socialId = socialId;
        this.socialProvider = socialProvider;
        this.role = role;
    }

    public static User socialSignup(SocialProvider socialProvider, String socialId, String email, String name) {
        return User.builder()
                .email(email)
                .name(resolveName(name))
                .socialId(socialId)
                .socialProvider(socialProvider)
                .role(Role.USER)
                .build();
    }

    public void updateSocialRefreshToken(String socialRefreshToken) {
        this.socialRefreshToken = socialRefreshToken;
    }

    private static String resolveName(String name) {
        if (name == null || name.isBlank()) {
            return DEFAULT_NAME;
        }
        return name.trim();
    }
}
