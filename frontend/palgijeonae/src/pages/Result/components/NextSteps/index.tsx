import type { ProductResult } from "@/api/product";
import NoticesSection from "@/pages/Result/components/NextSteps/components/NoticesSection";
import ReflectedAnswersSection from "@/pages/Result/components/NextSteps/components/ReflectedAnswersSection";
import RequiredActionsSection from "@/pages/Result/components/NextSteps/components/RequiredActionsSection";

interface NextStepTabProps {
    product: ProductResult
}

function NextStepTab({product}: NextStepTabProps) {
    return ( 
        <div className="flex flex-col w-full gap-10">
            <RequiredActionsSection requiredActions={product.requiredActions}/>
            <NoticesSection notices={product.notices}/>
            <ReflectedAnswersSection questions={product.questions}/>
        </div>
     );
}

export default NextStepTab;