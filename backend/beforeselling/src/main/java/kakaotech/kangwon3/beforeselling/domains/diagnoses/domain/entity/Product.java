package kakaotech.kangwon3.beforeselling.domains.diagnoses.domain.entity;

import jakarta.persistence.*;
import kakaotech.kangwon3.beforeselling.global.common.BaseEntity;
import kakaotech.kangwon3.beforeselling.global.common.CommonResponseCode;
import kakaotech.kangwon3.beforeselling.global.exception.BaseException;
import lombok.AccessLevel;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.BatchSize;

import java.util.ArrayList;
import java.util.List;
import org.hibernate.annotations.UuidGenerator;
import java.util.UUID;

@Entity
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@Table(
        name = "product",
        indexes = @Index(name = "idx_product_diagnoses_id_sort_order", columnList = "diagnoses_id, sort_order")
)
public class Product extends BaseEntity {

    // 질문을 받을 수 있는 마지막 회차. 질문은 첫 진단(0)에서 한 번만 받고, 재질문은 하지 않는다.
    public static final int MAX_QUESTION_ROUND = 0;

    @Id
    @UuidGenerator(style = UuidGenerator.Style.VERSION_7)
    @Column(name = "product_id")
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "diagnoses_id", nullable = false)
    private Diagnoses diagnoses;

    @Column(name = "sort_order", nullable = false)
    private int sortOrder;

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

    // 0: 첫 진단, 1: 질문 답변 후 재진단(반드시 결과로 끝난다).
    @Column(name = "diagnosis_round", nullable = false, columnDefinition = "integer default 0")
    private int diagnosisRound;

    @Column(name = "summary", columnDefinition = "TEXT")
    private String summary;

    @Column(name = "product_image_key", columnDefinition = "TEXT")
    private String productImageKey;

    // 진단서 -> 상품을 fetch join한 뒤 상품별 이미지를 지연 로딩할 때 쿼리가 N번 나가는 것을 막는다.
    @OneToMany(mappedBy = "product", cascade = CascadeType.ALL, orphanRemoval = true)
    @OrderBy("sortOrder ASC")
    @BatchSize(size = 100)
    private List<ProductImage> images = new ArrayList<>();

    // 카드와 질문은 fetch join하지 않는다. List 컬렉션을 둘 이상 함께 fetch join하면 MultipleBagFetchException 발생
    @OneToMany(mappedBy = "product", cascade = CascadeType.ALL, orphanRemoval = true)
    @BatchSize(size = 100)
    private List<AgentReview> agentReviews = new ArrayList<>();

    @OneToMany(mappedBy = "product", cascade = CascadeType.ALL, orphanRemoval = true)
    @OrderBy("questionOrder ASC")
    @BatchSize(size = 100)
    private List<ProductQuestion> questions = new ArrayList<>();

    @Builder(access = AccessLevel.PRIVATE)
    private Product(String productName, String productImageKey,
                    SourceType sourceType, String sourceUrl, String sourceText) {
        this.productName = productName;
        this.productImageKey = productImageKey;
        this.sourceType = sourceType;
        this.sourceUrl = sourceUrl;
        this.sourceText = sourceText;
        this.processingStatus = ProcessingStatus.PENDING;
    }

    public static Product pending(String productName, String productImageKey,
                                  SourceType sourceType, String sourceUrl, String sourceText) {
        return Product.builder()
                .productName(productName)
                .productImageKey(productImageKey)
                .sourceType(sourceType)
                .sourceUrl(sourceUrl)
                .sourceText(sourceText)
                .build();
    }

    public void addImages(List<String> imageKeys) {
        for (String imageKey : imageKeys) {
            images.add(new ProductImage(this, imageKey, images.size()));
        }
    }

    // Diagnoses.addProducts 에서만 호출한다. 상품은 진단서를 거쳐서만 연결되어야 한다.
    void assignTo(Diagnoses diagnoses, int sortOrder) {
        this.diagnoses = diagnoses;
        this.sortOrder = sortOrder;
    }

    public void startDiagnosis() {
        transition(ProcessingStatus.PENDING, ProcessingStatus.IN_PROGRESS);
    }

    public void awaitInput() {
        if (diagnosisRound > MAX_QUESTION_ROUND) {
            throw new BaseException(CommonResponseCode.CONFLICT);
        }
        transition(ProcessingStatus.IN_PROGRESS, ProcessingStatus.AWAITING_INPUT);
    }

    public void resume() {
        transition(ProcessingStatus.AWAITING_INPUT, ProcessingStatus.IN_PROGRESS);
        diagnosisRound++;
    }

    // 같은 에이전트의 카드가 이미 있으면 덮어쓴다(재진단 갱신, 콜백 중복 수신).
    // 동시에 들어온 콜백끼리 경쟁하지 않도록, 호출하는 쪽에서 진단서를 비관적 락으로 잡은 뒤 호출한다.
    public void recordAgentReview(AgentType agentType, AgentReviewStatus status, String description) {
        agentReviews.stream()
                .filter(review -> review.getAgentType() == agentType)
                .findFirst()
                .ifPresentOrElse(
                        review -> review.update(status, description),
                        () -> agentReviews.add(new AgentReview(this, agentType, status, description))
                );
    }

    // 질문은 첫 진단에서 한 번만 받고, 받으면 사용자 답변을 기다리는 상태가 된다.
    // 두 번째 호출은 상태(AWAITING_INPUT) 또는 회차 제한 때문에 awaitInput()에서 CONFLICT로 막힌다.
    public void askQuestions(List<QuestionContent> contents) {
        // 질문 없이 답변 대기가 되면 사용자가 답할 수 없어 진단이 멈춘다.
        if (contents.isEmpty()) {
            throw new BaseException(CommonResponseCode.BAD_REQUEST);
        }
        // 같은 키가 함께 오면 flush 시점의 유니크 제약 위반 대신 여기서 막는다.
        if (contents.stream().map(QuestionContent::questionKey).distinct().count() != contents.size()) {
            throw new BaseException(CommonResponseCode.BAD_REQUEST);
        }

        awaitInput();
        contents.forEach(content -> questions.add(new ProductQuestion(this, content.questionKey(),
                content.questionOrder(), content.questionText(), content.helpText())));
    }

    public void fail() {
        transition(ProcessingStatus.IN_PROGRESS, ProcessingStatus.FAILED);
    }

    private void transition(ProcessingStatus from, ProcessingStatus to) {
        if (processingStatus != from) {
            throw new BaseException(CommonResponseCode.CONFLICT);
        }
        this.processingStatus = to;
    }


    // 대표 이미지와 상세 이미지 key를 순서대로 모은다(S3 정리·확정 처리에 사용).
    public List<String> collectImageKeys() {
        List<String> keys = new ArrayList<>();
        if (productImageKey != null) {
            keys.add(productImageKey);
        }
        images.stream().map(ProductImage::getImageKey).forEach(keys::add);
        return keys;
    }
}
