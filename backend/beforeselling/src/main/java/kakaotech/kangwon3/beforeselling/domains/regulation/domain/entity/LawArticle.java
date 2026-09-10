package kakaotech.kangwon3.beforeselling.domains.regulation.domain.entity;

import java.time.LocalDate;
import java.time.OffsetDateTime;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;
import jakarta.persistence.UniqueConstraint;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Entity
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@Table(
        name = "law_articles",
        uniqueConstraints = @UniqueConstraint(
                name = "uk_law_articles_no_branch",
                columnNames = {"law_id", "article_no", "article_branch"}
        )
)
public class LawArticle {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "law_article_id")
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "law_id", nullable = false)
    private Law law;

    @Column(name = "article_no", nullable = false)
    private Integer articleNo;

    @Column(name = "article_branch")
    private Integer articleBranch;

    @Column(name = "title", length = 300)
    private String title;

    @Column(name = "full_text", columnDefinition = "TEXT", nullable = false)
    private String fullText;

    @Column(name = "enforcement_date")
    private LocalDate enforcementDate;

    @Column(name = "embedding", columnDefinition = "vector(1536)")
    private String embedding;

    @Column(name = "fetched_at", nullable = false)
    private OffsetDateTime fetchedAt;
}
