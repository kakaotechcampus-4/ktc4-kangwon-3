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
                        <DefaultBox key={index} className="flex-row items-center gap-3 md:gap-4">
                            <div className="flex size-7 shrink-0 items-center justify-center rounded-full bg-primary/10 text-sm leading-none font-semibold text-primary md:size-8 md:text-base">
                                {index + 1}
                            </div>
                            <p className="flex-1 text-[15px] leading-relaxed whitespace-pre-line text-black md:text-base">{action}</p>
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
