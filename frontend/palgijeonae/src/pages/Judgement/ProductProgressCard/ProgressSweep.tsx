/** 진행 중인 카드 상단을 따라 지나가는 라인. */
function ProgressSweep() {
    return (
        <span
            aria-hidden="true"
            className="pointer-events-none absolute top-0 left-0 z-10 h-0.5 w-2/5 bg-linear-to-r from-transparent via-primary to-transparent motion-safe:animate-progress-sweep"
        />
    );
}

export default ProgressSweep;
