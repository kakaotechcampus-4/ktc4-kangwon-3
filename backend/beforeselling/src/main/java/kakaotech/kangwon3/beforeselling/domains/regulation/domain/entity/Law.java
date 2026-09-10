package kakaotech.kangwon3.beforeselling.domains.regulation.domain.entity;

import java.time.LocalDate;
import java.time.OffsetDateTime;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Entity
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@Table(name = "laws")

public class Law {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "law_id")
    private Long id;

    @Column(name = "law_mst", length = 20, nullable = false, unique = true)
    private String lawMst;

    @Column(name = "law_code", length = 20, nullable = false)
    private String lawCode;

    @Column(name = "name_ko", length = 200, nullable = false)
    private String nameKo;

    @Column(name = "abbreviation", length = 100)
    private String abbreviation;

    @Column(name = "law_type", length = 30, nullable = false)
    private String lawType;

    @Column(name = "enforcement_date")
    private LocalDate enforcementDate;

    @Column(name = "competent_authority", length = 100)
    private String competentAuthority;

    @Column(name = "is_current", nullable = false)
    private Boolean isCurrent;

    @Column(name = "fetched_at", nullable = false)
    private OffsetDateTime fetchedAt;

}
