package kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity;

import jakarta.persistence.*;
import kakaotech.kangwon3.beforeselling.global.common.BaseEntity;
import lombok.AccessLevel;
import lombok.Builder;
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

    @Column(name = "product_name", nullable = false)
    private String productName;

    @Enumerated(EnumType.STRING)
    @Column(name = "source_type", nullable = false)
    private SourceType sourceType;

    @Column(name = "source_url", columnDefinition = "TEXT")
    private String sourceUrl;

    @Column(name = "source_text", columnDefinition = "TEXT")
    private String sourceText;

    @Enumerated(EnumType.STRING)
    @Column(name = "processing_status", nullable = false)
    private ProcessingStatus processingStatus;

    @Enumerated(EnumType.STRING)
    @Column(name = "result_status")
    private ResultStatus resultStatus;

    @Column(name = "summary", columnDefinition = "TEXT")
    private String summary;

    @Column(name = "product_image_key", columnDefinition = "TEXT")
    private String productImageKey;

    @OneToMany(mappedBy = "diagnoses", cascade = CascadeType.ALL, orphanRemoval = true)
    @OrderBy("sortOrder ASC")
    private List<DiagnosesImage> images = new ArrayList<>();

    @Builder(access = AccessLevel.PRIVATE)
    private Diagnoses(Long userId, String productName, String productImageKey,
                      SourceType sourceType, String sourceUrl, String sourceText) {
        this.userId = userId;
        this.productName = productName;
        this.productImageKey = productImageKey;
        this.sourceType = sourceType;
        this.sourceUrl = sourceUrl;
        this.sourceText = sourceText;
        this.processingStatus = ProcessingStatus.PENDING;
    }

    public static Diagnoses pending(Long userId, String productName, String productImageKey,
                                    SourceType sourceType, String sourceUrl, String sourceText) {
        return Diagnoses.builder()
                .userId(userId)
                .productName(productName)
                .productImageKey(productImageKey)
                .sourceType(sourceType)
                .sourceUrl(sourceUrl)
                .sourceText(sourceText)
                .build();
    }

    public void addImages(List<String> imageKeys) {
        for (String imageKey : imageKeys) {
            images.add(new DiagnosesImage(this, imageKey, images.size()));
        }
    }

    public boolean isOwnedBy(Long userId) {
        return this.userId.equals(userId);
    }
}
