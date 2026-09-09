package kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity;

import jakarta.persistence.*;
import kakaotech.kangwon3.beforeselling.domains.user.domain.entity.User;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Entity
@Getter
@NoArgsConstructor
public class Diagnoses {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, name = "user_id")
    private Long userId;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private SourceType sourceType;

    @Column
    private String sourceUrl;

    @Column
    private String sourceText;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private ProcessingStatus processingStatus;

    @Column
    private String summary;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private ResultStatus resultStatus;

    @Column(nullable = false)
    private String name;

    @Column
    private String productImageUrl;
}
