package kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.Id;
import jakarta.persistence.Index;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;
import kakaotech.kangwon3.beforeselling.global.common.BaseEntity;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.UuidGenerator;

import java.util.UUID;

// 판단 항목의 법령·기관 근거
@Entity
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@Table(
        name = "finding_legal_source",
        indexes = @Index(name = "idx_finding_legal_source_finding_id_sort_order",
                columnList = "product_finding_id, sort_order")
)
public class FindingLegalSource extends BaseEntity {

    @Id
    @UuidGenerator(style = UuidGenerator.Style.VERSION_7)
    @Column(name = "finding_legal_source_id")
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "product_finding_id", nullable = false)
    private ProductFinding finding;

    @Column(name = "sort_order", nullable = false)
    private int sortOrder;

    @Column(name = "source_name", nullable = false)
    private String sourceName;

    @Column(name = "law_name")
    private String lawName;

    @Column(name = "article")
    private String article;

    @Column(name = "quoted_text", columnDefinition = "TEXT")
    private String quotedText;

    @Column(name = "source_url", columnDefinition = "TEXT")
    private String sourceUrl;

    // AI가 형식 보장 없이 문자열로 주므로(예: "2026-01-01") 날짜로 해석하지 않고 그대로 보관
    @Column(name = "effective_date", length = 50)
    private String effectiveDate;

    FindingLegalSource(ProductFinding finding, int sortOrder, String sourceName, String lawName, String article,
                       String quotedText, String sourceUrl, String effectiveDate) {
        this.finding = finding;
        this.sortOrder = sortOrder;
        this.sourceName = sourceName;
        this.lawName = lawName;
        this.article = article;
        this.quotedText = quotedText;
        this.sourceUrl = sourceUrl;
        this.effectiveDate = effectiveDate;
    }

    static FindingLegalSource of(ProductFinding finding, int sortOrder, AssessmentContent.LegalSourceContent content) {
        return new FindingLegalSource(finding, sortOrder, content.sourceName(), content.lawName(),
                content.article(), content.quotedText(), content.sourceUrl(), content.effectiveDate());
    }
}
