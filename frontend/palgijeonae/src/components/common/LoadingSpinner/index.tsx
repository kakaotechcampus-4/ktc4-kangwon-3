interface LoadingSpinnerProps {
    label?: string
}

function LoadingSpinner({ label }: LoadingSpinnerProps) {
    return (
        <div role="status" aria-label={label ?? "로딩 중"} className="flex w-full flex-col items-center justify-center gap-4 py-12">
            <div className="h-10 w-10 animate-spin rounded-full border-4 border-neutral-border border-t-white" />
            {label && <p className="text-lg text-neutral-text">{label}</p>}
        </div>
    );
}

export default LoadingSpinner;
