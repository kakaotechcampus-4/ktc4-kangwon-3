interface RequiredActionsSectionProps {
    requiredActions: string[]
}

// TODO: 번호 리스트로 렌더링하고, 빈 배열이면 "해야 할 일 없음" 안내로 교체
function RequiredActionsSection({ requiredActions }: RequiredActionsSectionProps) {
    return (
        <div>
            해야 할 일 섹션입니다. ({requiredActions.length}건)
        </div>
    );
}

export default RequiredActionsSection;
