import type { LegalSource } from "@/api/product";

enum LawCardField {
    Source = "source",
    LawArticle = "lawArticle",
    EffectiveDate = "effectiveDate",
    QuotedText = "quotedText",
}

// 라벨+값 한 줄로만 끝나는 필드들의 라벨과 표시 순서
const FIELD_LABELS: Record<LawCardField, string> = {
    [LawCardField.Source]: "출처",
    [LawCardField.LawArticle]: "근거조문",
    [LawCardField.EffectiveDate]: "시행일",
    [LawCardField.QuotedText]: "조항 원문",
};

const FIELD_ORDER: LawCardField[] = [
    LawCardField.Source,
    LawCardField.LawArticle,
    LawCardField.EffectiveDate,
    LawCardField.QuotedText,
];

interface LawCardProps {
    legalSource: LegalSource
}

function LawCard({ legalSource }: LawCardProps) {
    const { sourceName, lawName, article, quotedText, sourceUrl, effectiveDate } = legalSource;
    const lawNameAndArticle = [lawName, article].filter(Boolean).join(" ");

    const fieldValues: Record<LawCardField, string | null> = {
        [LawCardField.Source]: sourceName,
        [LawCardField.LawArticle]: lawNameAndArticle,
        [LawCardField.EffectiveDate]: effectiveDate,
        [LawCardField.QuotedText]: quotedText,
    };

    return (
        <div className="flex w-full flex-col gap-3 rounded-2xl border border-neutral-border px-6 py-4.5">
            {FIELD_ORDER.filter((field) => fieldValues[field]).map((field) => (
                <div key={field} className="flex items-center gap-4">
                    <p className="w-21 shrink-0 text-sm font-bold text-neutral-muted">{FIELD_LABELS[field]}</p>
                    <p className="text-sm text-black">{fieldValues[field]}</p>
                </div>
            ))}
            {sourceUrl && (
                <div className="pl-25">
                    <a href={sourceUrl} target="_blank" rel="noreferrer" className="text-sm font-medium text-primary">
                        법령 원문 보기
                    </a>
                </div>
            )}
        </div>
    );
}

export default LawCard;
