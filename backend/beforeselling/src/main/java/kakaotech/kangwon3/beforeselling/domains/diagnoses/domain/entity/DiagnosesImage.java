package kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity;

import jakarta.persistence.*;
import kakaotech.kangwon3.beforeselling.global.common.BaseEntity;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Entity
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@Table(name = "diagnoses_image")
public class DiagnosesImage extends BaseEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "diagnoses_image_id")
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "diagnoses_id", nullable = false)
    private Diagnoses diagnoses;

    @Column(name = "image_url", nullable = false, columnDefinition = "TEXT")
    private String imageUrl;

    // BE -> AI OCR 깨짐 방지를 위하여
    @Column(name = "sort_order", nullable = false)
    private int sortOrder;

    DiagnosesImage(Diagnoses diagnoses, String imageUrl, int sortOrder) {
        this.diagnoses = diagnoses;
        this.imageUrl = imageUrl;
        this.sortOrder = sortOrder;
    }
}
