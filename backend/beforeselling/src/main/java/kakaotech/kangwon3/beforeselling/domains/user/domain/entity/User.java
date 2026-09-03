package kakaotech.kangwon3.beforeselling.domains.user.domain.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import jakarta.persistence.UniqueConstraint;
import kakaotech.kangwon3.beforeselling.global.common.BaseEntity;
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

    private static String resolveName(String name) {
        if (name == null || name.isBlank()) {
            return DEFAULT_NAME;
        }
        return name.trim();
    }
}
