package kakaotech.kangwon3.beforeselling.global.infra.s3.domain.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Index;
import jakarta.persistence.Table;
import kakaotech.kangwon3.beforeselling.global.common.BaseEntity;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Entity
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@Table(
        name = "s3_files",
        indexes = @Index(name = "idx_s3_files_status_created_at", columnList = "status, created_at")
)
public class S3File extends BaseEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "s3_file_id")
    private Long id;

    @Column(name = "key", nullable = false, unique = true, length = 2048)
    private String key;

    @Enumerated(EnumType.STRING)
    @Column(name = "status", nullable = false)
    private S3FileStatus status;

    private S3File(String key) {
        this.key = key;
        this.status = S3FileStatus.PENDING;
    }

    public static S3File pending(String key) {
        return new S3File(key);
    }

    public void confirm() {
        this.status = S3FileStatus.CONFIRMED;
    }
}
