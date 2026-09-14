package kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity;

import jakarta.persistence.*;
import kakaotech.kangwon3.beforeselling.global.common.BaseEntity;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Entity
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@Table(
        name = "diagnoses_image",
        indexes = @Index(name = "idx_diagnoses_image_diagnoses_id", columnList = "diagnoses_id")
)
public class DiagnosesImage extends BaseEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "diagnoses_image_id")
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "diagnoses_id", nullable = false)
    private Diagnoses diagnoses;

    @Column(name = "image_key", nullable = false, columnDefinition = "TEXT")
    private String imageKey;

    // BE -> AI OCR 깨짐 방지를 위하여
    @Column(name = "sort_order", nullable = false)
    private int sortOrder;

    DiagnosesImage(Diagnoses diagnoses, String imageKey, int sortOrder) {
        this.diagnoses = diagnoses;
        this.imageKey = imageKey;
        this.sortOrder = sortOrder;
    }
}
