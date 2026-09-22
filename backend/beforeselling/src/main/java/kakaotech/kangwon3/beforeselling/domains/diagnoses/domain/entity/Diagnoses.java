package kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity;

import jakarta.persistence.*;
import kakaotech.kangwon3.beforeselling.global.common.BaseEntity;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;

import java.util.ArrayList;
import java.util.List;

@Entity
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@Table(
        name = "diagnoses",
        indexes = @Index(name = "idx_diagnoses_user_id_created_at", columnList = "user_id, created_at")
)
public class Diagnoses extends BaseEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "diagnoses_id")
    private Long id;

    @Column(name = "user_id", nullable = false)
    private Long userId;

    @Enumerated(EnumType.STRING)
    @Column(name = "processing_status", nullable = false)
    private ProcessingStatus processingStatus;

    @OneToMany(mappedBy = "diagnoses", cascade = CascadeType.ALL, orphanRemoval = true)
    @OrderBy("sortOrder ASC")
    private List<Product> products = new ArrayList<>();

    private Diagnoses(Long userId) {
        this.userId = userId;
        this.processingStatus = ProcessingStatus.PENDING;
    }

    public static Diagnoses pending(Long userId) {
        return new Diagnoses(userId);
    }

    // 업로드한 순서를 sortOrder로 고정한다(판정 페이지 제품 탭 순서).
    public void addProducts(List<Product> newProducts) {
        for (Product product : newProducts) {
            product.assignTo(this, products.size());
            products.add(product);
        }
    }

    public boolean isOwnedBy(Long userId) {
        return this.userId.equals(userId);
    }

    /**
     * 상품들의 상태로 진단서 전체 상태를 다시 계산한다.
     */
    public void refreshProcessingStatus() {
        this.processingStatus = calculateProcessingStatus();
    }

    private ProcessingStatus calculateProcessingStatus() {
        if (hasAny(ProcessingStatus.AWAITING_INPUT)) {
            return ProcessingStatus.AWAITING_INPUT;
        }
        if (hasAny(ProcessingStatus.PENDING) || hasAny(ProcessingStatus.IN_PROGRESS)) {
            return ProcessingStatus.IN_PROGRESS;
        }
        // 일부만 실패한 경우는 진단서 자체는 끝난 것으로 보고, 실패는 상품 단위로 표시한다.
        if (products.stream().allMatch(product -> product.getProcessingStatus() == ProcessingStatus.FAILED)) {
            return ProcessingStatus.FAILED;
        }
        return ProcessingStatus.COMPLETED;
    }

    private boolean hasAny(ProcessingStatus status) {
        return products.stream().anyMatch(product -> product.getProcessingStatus() == status);
    }
}