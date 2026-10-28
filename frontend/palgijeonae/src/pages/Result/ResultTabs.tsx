import { cva } from "class-variance-authority";

import diagnosisResultIcon from "@/assets/result-diagnosisResult.svg";
import diagnosisResultIconBlue from "@/assets/result-diagnosisResult-blue.svg";
import nextStepIcon from "@/assets/result-nextStep.svg";
import nextStepIconBlue from "@/assets/result-nextStep-blue.svg";
import productInfoIcon from "@/assets/result-productInfo.svg";
import productInfoIconBlue from "@/assets/result-productInfo-blue.svg";
import { cn } from "@/lib/cn";

import { ResultTabKey } from "./types";

interface TabInfo {
    icon: string
    iconSelected: string
    label: string
}

// 탭 기본 아이콘 / 선택 시 아이콘 / 라벨
const TAB_INFO: Record<ResultTabKey, TabInfo> = {
    [ResultTabKey.DiagnosisResult]: { icon: diagnosisResultIcon, iconSelected: diagnosisResultIconBlue, label: "진단 결과" },
    [ResultTabKey.NextSteps]: { icon: nextStepIcon, iconSelected: nextStepIconBlue, label: "다음 단계" },
    [ResultTabKey.ProductInfo]: { icon: productInfoIcon, iconSelected: productInfoIconBlue, label: "상품 정보" },
};

const TAB_ORDER: ResultTabKey[] = [ResultTabKey.DiagnosisResult, ResultTabKey.NextSteps, ResultTabKey.ProductInfo];

const tabVariants = cva("flex items-center gap-1.25 px-0.5 py-1.25 border-b-2 text-base font-bold", {
    variants: {
        selected: {
            true: "border-primary text-primary",
            false: "border-transparent text-neutral-border",
        },
        disabled: {
            true: "cursor-not-allowed opacity-40",
            false: "cursor-pointer",
        },
    },
});

interface ResultTabsProps {
    selected: ResultTabKey
    onSelect: (tab: ResultTabKey) => void
    disabledTabs?: ResultTabKey[]
}

function ResultTabs({ selected, onSelect, disabledTabs = [] }: ResultTabsProps) {
    return (
        <div role="tablist" className="flex items-start gap-7.5 border-b border-neutral-border px-2.5">
            {TAB_ORDER.map((tab) => {
                const isSelected = tab === selected;
                const isDisabled = disabledTabs.includes(tab);
                const info = TAB_INFO[tab];
                return (
                    <button
                        key={tab}
                        type="button"
                        role="tab"
                        aria-selected={isSelected}
                        disabled={isDisabled}
                        onClick={() => onSelect(tab)}
                        className={cn(tabVariants({ selected: isSelected, disabled: isDisabled }))}
                    >
                        <img src={isSelected ? info.iconSelected : info.icon} alt="" className="h-7.5 w-7.5" />
                        {info.label}
                    </button>
                );
            })}
        </div>
    );
}

export default ResultTabs;
