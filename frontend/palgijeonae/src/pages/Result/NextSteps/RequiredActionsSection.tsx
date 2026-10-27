import DefaultBox from "@/components/common/DefaultBox";
import SectionIntro from "@/components/common/SectionIntro";

interface RequiredActionsSectionProps {
    requiredActions: string[]
}

function RequiredActionsSection({ requiredActions }: RequiredActionsSectionProps) {
    return (
        <div className="flex w-full flex-col gap-6">
            <SectionIntro title="해야 할 일" description="진단 결과에 따라 판매 전에 처리해야 할 조치예요." size="2xl"/>
            <div className="flex w-full flex-col gap-4">
                {requiredActions.length > 0 ? (
                    requiredActions.map((action, index) => (
                        <DefaultBox key={index} className="flex-row items-center gap-4">
                            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-neutral-text bg-white">
                                <span className="text-sm leading-tight font-bold text-neutral-text">{index + 1}</span>
                            </div>
                            <p className="flex-1 text-base leading-relaxed text-black">{action}</p>
                        </DefaultBox>
                    ))
                ) : (
                    <p className="w-full py-6 text-center text-sm font-medium text-neutral-border">
                        해야 할 일이 없어요.
                    </p>
                )}
            </div>
        </div>
    );
}

export default RequiredActionsSection;
