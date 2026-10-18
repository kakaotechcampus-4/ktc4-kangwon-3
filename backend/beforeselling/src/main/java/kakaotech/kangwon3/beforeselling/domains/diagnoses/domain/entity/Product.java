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

    // AI 실행 식별자. 진단 요청·재실행 요청의 202 응답으로 받는다. 받기 전에는 null
    @Column(name = "run_id")
    private String runId;

    @Enumerated(EnumType.STRING)
    @Column(name = "failed_stage")
    private PipelineStage failedStage;

    @Column(name = "error_code", length = 50)
    private String errorCode;

    @Column(name = "error_message", columnDefinition = "TEXT")
    private String errorMessage;

    @Column(name = "error_retryable")
    private Boolean errorRetryable;

    // 결과를 받기 전에는 null
    @Enumerated(EnumType.STRING)
    @Column(name = "assessment_status")
    private AssessmentStatus assessmentStatus;

    @Enumerated(EnumType.STRING)
    @Column(name = "result_status")
    private ResultStatus resultStatus;

    @Column(name = "summary", columnDefinition = "TEXT")
    private String summary;

    @Column(name = "product_image_key", columnDefinition = "TEXT")
    private String productImageKey;

    // 진단서 -> 상품을 fetch join한 뒤 상품별 이미지를 지연 로딩할 때 쿼리가 N번 나가는 것을 막는다.
    @OneToMany(mappedBy = "product", cascade = CascadeType.ALL, orphanRemoval = true)
    @OrderBy("sortOrder ASC")
    @BatchSize(size = 100)
    private List<ProductImage> images = new ArrayList<>();

    // 질문과 결과 컬렉션은 fetch join하지 않는다. List 컬렉션을 둘 이상 함께 fetch join하면 MultipleBagFetchException 발생
    @OneToMany(mappedBy = "product", cascade = CascadeType.ALL, orphanRemoval = true)
    @OrderBy("questionRound ASC, questionOrder ASC")
    @BatchSize(size = 100)
    private List<ProductQuestion> questions = new ArrayList<>();

    // 진행 콜백의 단계·툴별 최신 상태. 진행 화면에서 읽는다.
    @OneToMany(mappedBy = "product", cascade = CascadeType.ALL, orphanRemoval = true)
    @BatchSize(size = 100)
    private List<ProductProgress> progresses = new ArrayList<>();

    // 이하 진단 결과. 분야별 카드는 결과 콜백으로만 채운다(진행 콜백에는 카드 내용이 없다).
    @OneToMany(mappedBy = "product", cascade = CascadeType.ALL, orphanRemoval = true)
    @BatchSize(size = 100)
    private List<ProductToolReview> toolReviews = new ArrayList<>();

    @ElementCollection
    @CollectionTable(name = "product_required_action", joinColumns = @JoinColumn(name = "product_id"))
    @OrderColumn(name = "action_order")
    @Column(name = "action_text", nullable = false, columnDefinition = "TEXT")
    @BatchSize(size = 100)
    private List<String> requiredActions = new ArrayList<>();

    @ElementCollection
    @CollectionTable(name = "product_notice", joinColumns = @JoinColumn(name = "product_id"))
    @OrderColumn(name = "notice_order")
    @Column(name = "notice_text", nullable = false, columnDefinition = "TEXT")
    @BatchSize(size = 100)
    private List<String> notices = new ArrayList<>();

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

    public void startDiagnoses() {
        transition(ProcessingStatus.PENDING, ProcessingStatus.IN_PROGRESS);
    }

    public void resume() {
        transition(ProcessingStatus.AWAITING_INPUT, ProcessingStatus.IN_PROGRESS);
    }
    
    public void assignRun(String runId) {
        if (runId == null || runId.isBlank()) {
            throw new BaseException(CommonResponseCode.BAD_REQUEST);
        }
        if (processingStatus != ProcessingStatus.IN_PROGRESS) {
            throw new BaseException(CommonResponseCode.CONFLICT);
        }
        this.runId = runId;
    }

    public boolean isCurrentRun(String runId) {
        return this.runId != null && this.runId.equals(runId);
    }

    // 202 응답의 runId를 아직 저장하지 못한 상태. 이때 온 콜백은 다시 보내 달라고 한다.
    public boolean isRunAssigned() {
        return runId != null;
    }

    // 같은 실행에서 이미 반영한 것보다 앞선 이벤트(재시도로 늦게 온 것, 중복)는 무시한다.
    public void recordProgress(String runId, int sequence, PipelineStage stage,
                               StageStatus stageStatus, ToolName toolName) {
        if (toolName != null && stage != PipelineStage.TOOL_EXECUTION) {
            throw new BaseException(CommonResponseCode.BAD_REQUEST);
        }
        if (processingStatus != ProcessingStatus.IN_PROGRESS) {
            throw new BaseException(CommonResponseCode.CONFLICT);
        }

        progresses.stream()
                .filter(progress -> progress.isFor(stage, toolName))
                .findFirst()
                .ifPresentOrElse(
                        progress -> {
                            if (!progress.isNewerOrSame(runId, sequence)) {
                                progress.update(runId, sequence, stageStatus);
                            }
                        },
                        () -> progresses.add(new ProductProgress(this, runId, sequence, stage, stageStatus, toolName))
                );
    }

    // 질문을 받으면 사용자 답변을 기다리는 상태가 된다.
    // BE는 AI가 보낸 회차를 그대로 저장한다.
    // 답변 대기 중에 다시 질문이 오면 상태 전이(IN_PROGRESS → AWAITING_INPUT)에서 CONFLICT로 막힌다.
    public void askQuestions(int questionRound, List<QuestionContent> contents) {
        // 질문 없이 답변 대기가 되면 사용자가 답할 수 없어 진단이 멈춘다.
        if (contents.isEmpty()) {
            throw new BaseException(CommonResponseCode.BAD_REQUEST);
        }
        // 같은 키가 함께 오면 flush 시점의 유니크 제약 위반 대신 여기서 막는다.
        if (contents.stream().map(QuestionContent::questionKey).distinct().count() != contents.size()) {
            throw new BaseException(CommonResponseCode.BAD_REQUEST);
        }
        
        transition(ProcessingStatus.IN_PROGRESS, ProcessingStatus.AWAITING_INPUT);
        contents.forEach(content -> questions.add(new ProductQuestion(this, questionRound,
                content.questionKey(), content.questionOrder(), content.questionText(), content.helpText())));
    }

    // 진단을 실패로 끝내고 실패 정보를 남긴다.
    public void fail(PipelineStage failedStage, String errorCode, String errorMessage, Boolean errorRetryable) {
        if (errorCode == null || errorCode.isBlank() || errorMessage == null || errorMessage.isBlank()) {
            throw new BaseException(CommonResponseCode.BAD_REQUEST);
        }

        transition(ProcessingStatus.IN_PROGRESS, ProcessingStatus.FAILED);
        this.failedStage = failedStage;
        this.errorCode = errorCode;
        this.errorMessage = errorMessage;
        this.errorRetryable = errorRetryable;
    }

    // 진단 결과를 반영하고 완료 상태로 끝낸다.
    public void complete(AssessmentContent content) {
        transition(ProcessingStatus.IN_PROGRESS, ProcessingStatus.COMPLETED);

        this.assessmentStatus = content.status();
        this.resultStatus = content.resultStatus();
        this.summary = content.summary();
        content.toolReviews().forEach(review -> toolReviews.add(ProductToolReview.of(this, review)));
        requiredActions.addAll(content.requiredActions());
        notices.addAll(content.notices());
    }

    public boolean hasResult() {
        return processingStatus == ProcessingStatus.COMPLETED;
    }

    // open-in-view=false 라 DTO 매핑 전에 트랜잭션 안에서 상세 응답에 필요한 컬렉션(이미지, 진단 결과)을 미리 읽어 둠.
    public void loadDetail() {
        images.size();
        toolReviews.forEach(review ->
                review.getFindings().forEach(finding -> finding.getLegalSources().size()));
        requiredActions.size();
        notices.size();
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
