import DefaultBox from "@/components/common/DefaultBox/index.tsx";
import type { PolicySummary as PolicySummaryData } from "@/pages/Policy/types.ts";

interface PolicySummaryProps {
    summary: PolicySummaryData
}

function PolicySummary({ summary }: PolicySummaryProps) {
    if (summary.kind === "notice") {
        return (
            <DefaultBox tone="warning" className="gap-1.5 px-4.5 py-4 md:px-6 md:py-4.5">
                <p className="text-[15px] font-bold text-status-warning">{summary.title}</p>
                {summary.paragraphs.map((paragraph) => (
                    <p key={paragraph} className="text-sm leading-5.5 text-neutral-text md:text-[15px] md:leading-6">
                        {paragraph}
                    </p>
                ))}
            </DefaultBox>
        );
    }

    return (
        <div className="flex w-full flex-col gap-3.5 rounded-xl border border-primary/20 bg-primary-soft px-4.5 py-4 md:px-6 md:py-4.5">
            <p className="text-[15px] font-bold text-primary">{summary.title}</p>
            <ul className="grid gap-2 md:grid-cols-3 md:gap-3">
                {summary.highlights.map(({ label, value }) => (
                    <li key={label} className="flex flex-col gap-1 rounded-lg bg-white px-4 py-3">
                        <span className="text-[13px] text-neutral-label">{label}</span>
                        <span className="text-[15px] font-bold text-black">{value}</span>
                    </li>
                ))}
            </ul>
        </div>
    );
}

export default PolicySummary;
