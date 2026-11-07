import { cn } from "@/lib/cn";

interface AgentCardProps {
    icon: string
    name: string
    role: string
    description: string
    chips: string[]
    alwaysCheckTag?: string
    reverse: boolean
}

/** 에이전트 소개 카드 1장. 아이콘·이름·역할 패널과 설명·키워드 칩을 좌우로 나란히 보여주고, reverse면 좌우를 뒤집는다. */
function AgentCard({ icon, name, role, description, chips, alwaysCheckTag, reverse }: AgentCardProps) {
    return (
        <div
            className={cn(
                "grid items-center gap-7 rounded-3xl border border-box-line bg-white p-7 shadow-box",
                reverse ? "grid-cols-[minmax(0,1.2fr)_minmax(0,0.8fr)]" : "grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)]",
            )}
        >
            <div className={cn("flex h-full flex-col items-start justify-center gap-4 rounded-3xl bg-primary-soft px-6 py-7", reverse && "order-2")}>
                <div className="grid size-16 shrink-0 place-items-center rounded-full bg-primary">
                    <img src={icon} alt="" className="size-8" />
                </div>
                <div>
                    <p className="text-xl font-bold text-black">{name}</p>
                    <p className="mt-0.5 text-sm text-neutral-text">{role}</p>
                </div>
                {alwaysCheckTag && (
                    <span className="rounded-full bg-primary-soft px-2 py-0.5 text-xs font-semibold text-primary">{alwaysCheckTag}</span>
                )}
            </div>
            <div className="flex flex-col gap-3.5">
                <p className="whitespace-pre-line text-base font-medium leading-relaxed text-neutral-text">{description}</p>
                <div className="flex flex-wrap gap-1.5">
                    {chips.map((chip) => (
                        <span key={chip} className="rounded-full border border-box-line px-3 py-1 text-xs text-neutral-dark">
                            {chip}
                        </span>
                    ))}
                </div>
            </div>
        </div>
    );
}

export default AgentCard;
