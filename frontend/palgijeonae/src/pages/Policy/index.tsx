import { useParams } from "react-router-dom";

import SectionIntro from "@/components/common/SectionIntro/index.tsx";
import type { PolicyType } from "@/constants/navigation.ts";
import NotFoundPage from "@/pages/NotFound/index.tsx";
import PolicyBody from "@/pages/Policy/components/PolicyBody.tsx";
import PolicySummary from "@/pages/Policy/components/PolicySummary.tsx";
import PolicyTabs from "@/pages/Policy/components/PolicyTabs.tsx";
import PolicyToc from "@/pages/Policy/components/PolicyToc.tsx";
import { POLICY_DOCUMENTS } from "@/pages/Policy/constants.ts";

const isPolicyType = (value: string | undefined): value is PolicyType => value !== undefined && Object.keys(POLICY_DOCUMENTS).includes(value);

/** 이용약관·개인정보처리방침 페이지. 로그인 없이 볼 수 있고, `/policy/:type`으로 두 문서를 나눠 보여준다. */
function PolicyPage() {
    const { type } = useParams<{ type?: string }>();

    if (!isPolicyType(type)) {
        return <NotFoundPage />;
    }

    const policy = POLICY_DOCUMENTS[type];

    return (
        <div className="flex w-full flex-col gap-6 md:gap-8">
            <SectionIntro title={policy.title} description={`시행일 ${policy.effectiveDate}`} />
            <PolicyTabs />
            <PolicySummary summary={policy.summary} />
            <PolicyToc sections={policy.sections} />
            <PolicyBody sections={policy.sections} />
            <p className="text-sm leading-5 whitespace-pre-wrap text-neutral-label">{policy.footnote}</p>
        </div>
    );
}

export default PolicyPage;
