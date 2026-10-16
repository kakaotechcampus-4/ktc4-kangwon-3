package kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity;

import jakarta.persistence.CascadeType;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.FetchType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.OneToMany;
import jakarta.persistence.OrderBy;
import jakarta.persistence.Table;
import jakarta.persistence.UniqueConstraint;
import kakaotech.kangwon3.beforeselling.global.common.BaseEntity;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.BatchSize;
import org.hibernate.annotations.UuidGenerator;

import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

// 진단 결과의 분야별 카드. 결과 콜백으로 한 번에 채워진다.
@Entity
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@Table(
        name = "product_tool_review",
        uniqueConstraints = @UniqueConstraint(
                name = "uk_product_tool_review_product_id_tool_name",
                columnNames = {"product_id", "tool_name"}
        )
)
public class ProductToolReview extends BaseEntity {

    @Id
    @UuidGenerator(style = UuidGenerator.Style.VERSION_7)
    @Column(name = "product_tool_review_id")
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "product_id", nullable = false)
    private Product product;

    @Enumerated(EnumType.STRING)
    @Column(name = "tool_name", nullable = false)
    private ToolName toolName;

    @Enumerated(EnumType.STRING)
    @Column(name = "status", nullable = false)
    private ToolReviewStatus status;

    @Column(name = "message", columnDefinition = "TEXT")
    private String message;

    @OneToMany(mappedBy = "toolReview", cascade = CascadeType.ALL, orphanRemoval = true)
    @OrderBy("sortOrder ASC")
    @BatchSize(size = 100)
    private List<ProductFinding> findings = new ArrayList<>();

    ProductToolReview(Product product, ToolName toolName, ToolReviewStatus status, String message) {
        this.product = product;
        this.toolName = toolName;
        this.status = status;
        this.message = message;
    }

    // 판단 항목은 받은 순서를 sortOrder로 고정한다.
    static ProductToolReview of(Product product, AssessmentContent.ToolReviewContent content) {
        ProductToolReview review = new ProductToolReview(product, content.toolName(), content.status(), content.message());
        content.findings().forEach(finding ->
                review.findings.add(ProductFinding.of(review, review.findings.size(), finding)));
        return review;
    }
}
