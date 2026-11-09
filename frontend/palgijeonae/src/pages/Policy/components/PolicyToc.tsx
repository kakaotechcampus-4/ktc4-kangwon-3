import DefaultBox from "@/components/common/DefaultBox/index.tsx";
import type { PolicySection } from "@/pages/Policy/types.ts";

interface PolicyTocProps {
    sections: PolicySection[]
}

// 화면이 좁은 모바일에서는 목차 없이 본문만 보여준다.
function PolicyToc({ sections }: PolicyTocProps) {
    return (
        <DefaultBox className="hidden gap-2.5 px-6 py-4.5 md:flex">
            <p className="text-[15px] font-bold text-black">목차</p>
            <nav aria-label="목차">
                <ul className="flex flex-col gap-1.5 text-sm text-neutral-muted">
                    {sections.map(({ id, heading }) => (
                        <li key={id}>
                            <a href={`#${id}`}>{heading}</a>
                        </li>
                    ))}
                </ul>
            </nav>
        </DefaultBox>
    );
}

export default PolicyToc;
