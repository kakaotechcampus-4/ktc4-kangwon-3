package kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity;

import jakarta.persistence.CascadeType;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.FetchType;
import jakarta.persistence.Id;
import jakarta.persistence.Index;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.OneToMany;
import jakarta.persistence.OrderBy;
import jakarta.persistence.Table;
import kakaotech.kangwon3.beforeselling.global.common.BaseEntity;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.BatchSize;
import org.hibernate.annotations.UuidGenerator;

import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

// 결과 카드 안의 판단 항목 하나. AI가 식별자를 주지 않으므로 받은 순서(sortOrder)로만 구분한다.
@Entity
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@Table(
        name = "product_finding",
        indexes = @Index(name = "idx_product_finding_tool_review_id_sort_order",
                columnList = "product_tool_review_id, sort_order")
)
public class ProductFinding extends BaseEntity {

    @Id
    @UuidGenerator(style = UuidGenerator.Style.VERSION_7)
    @Column(name = "product_finding_id")
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "product_tool_review_id", nullable = false)
    private ProductToolReview toolReview;

    @Column(name = "sort_order", nullable = false)
    private int sortOrder;

    @Column(name = "subject", nullable = false)
    private String subject;

    @Enumerated(EnumType.STRING)
    @Column(name = "determination", nullable = false)
    private Determination determination;

    @Enumerated(EnumType.STRING)
    @Column(name = "risk_level", nullable = false)
    private RiskLevel riskLevel;

    @Column(name = "summary", nullable = false, columnDefinition = "TEXT")
    private String summary;

    @Column(name = "rationale", nullable = false, columnDefinition = "TEXT")
    private String rationale;

    @OneToMany(mappedBy = "finding", cascade = CascadeType.ALL, orphanRemoval = true)
    @OrderBy("sortOrder ASC")
    @BatchSize(size = 100)
    private List<FindingLegalSource> legalSources = new ArrayList<>();

    ProductFinding(ProductToolReview toolReview, int sortOrder, String subject, Determination determination,
                   RiskLevel riskLevel, String summary, String rationale) {
        this.toolReview = toolReview;
        this.sortOrder = sortOrder;
        this.subject = subject;
        this.determination = determination;
        this.riskLevel = riskLevel;
        this.summary = summary;
        this.rationale = rationale;
    }

    static ProductFinding of(ProductToolReview toolReview, int sortOrder, AssessmentContent.FindingContent content) {
        ProductFinding finding = new ProductFinding(toolReview, sortOrder, content.subject(),
                content.determination(), content.riskLevel(), content.summary(), content.rationale());
        content.legalSources().forEach(source ->
                finding.legalSources.add(FindingLegalSource.of(finding, finding.legalSources.size(), source)));
        return finding;
    }
}
