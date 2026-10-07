package kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.FetchType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;
import jakarta.persistence.UniqueConstraint;
import kakaotech.kangwon3.beforeselling.global.common.BaseEntity;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.UuidGenerator;

import java.util.UUID;

@Entity
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@Table(
        name = "agent_review",
        uniqueConstraints = @UniqueConstraint(
                name = "uk_agent_review_product_id_agent_type",
                columnNames = {"product_id", "agent_type"}
        )
)
public class AgentReview extends BaseEntity {

    @Id
    @UuidGenerator(style = UuidGenerator.Style.VERSION_7)
    @Column(name = "agent_review_id")
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "product_id", nullable = false)
    private Product product;

    @Enumerated(EnumType.STRING)
    @Column(name = "agent_type", nullable = false)
    private AgentType agentType;

    @Enumerated(EnumType.STRING)
    @Column(name = "status", nullable = false)
    private AgentReviewStatus status;

    @Column(name = "description", columnDefinition = "TEXT")
    private String description;

    AgentReview(Product product, AgentType agentType, AgentReviewStatus status, String description) {
        this.product = product;
        this.agentType = agentType;
        this.status = status;
        this.description = description;
    }

    void update(AgentReviewStatus status, String description) {
        this.status = status;
        this.description = description;
    }
}
