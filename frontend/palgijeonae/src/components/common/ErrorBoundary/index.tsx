import { Component, type ReactNode } from "react";

import Button from "@/components/common/Button";

interface ErrorBoundaryProps {
    children: ReactNode
}

interface ErrorBoundaryState {
    hasError: boolean
}

/**
 * 렌더 중 발생한 에러를 잡아 폴백 화면을 보여준다.
 * Sentry 전송은 여기서 하지 않는다 — main.tsx의 createRoot onCaughtError(Sentry.reactErrorHandler())가
 * 이 바운더리가 잡는 에러도 함께 중앙에서 보고하므로, 여기서 또 보내면 같은 에러가 중복으로 올라간다.
 */
class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
    state: ErrorBoundaryState = { hasError: false };

    static getDerivedStateFromError() {
        return { hasError: true };
    }

    render() {
        if (this.state.hasError) {
            return (
                <div className="flex w-full flex-col items-center justify-center gap-6 py-24">
                    <p className="text-lg font-medium text-neutral-text">예상치 못한 오류가 발생했어요.</p>
                    <Button text="메인으로 돌아가기" onClick={() => { window.location.href = "/"; }} fontSize={15} />
                </div>
            );
        }

        return this.props.children;
    }
}

export default ErrorBoundary;
