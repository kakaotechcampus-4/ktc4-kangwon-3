import { getErrorMessage } from "@/api/core/client.ts";
import { useWithdraw } from "@/pages/Mypage/hooks/useWithdraw.ts";

const WITHDRAW_CONFIRM_MESSAGE = `정말 탈퇴할까요?

탈퇴하면 아래 데이터가 바로 삭제되고, 같은 소셜 계정으로 다시 가입해도 복구되지 않아요.

- 회원 정보(이름, 이메일, 연결된 소셜 계정)
- 지금까지 진단한 모든 상품과 진단 결과
- 상품 등록 때 첨부한 이미지`;

/** 마이페이지 맨 아래의 회원 탈퇴 영역. */
function WithdrawSection() {
    const { mutate: withdraw, isPending } = useWithdraw();

    const handleWithdraw = () => {
        if (!confirm(WITHDRAW_CONFIRM_MESSAGE)) {
            return;
        }

        withdraw(undefined, {
            onError: (error) => {
                alert(getErrorMessage(error, "탈퇴에 실패했습니다. 다시 시도해주세요."));
            },
        });
    };

    return (
        <div className="flex w-full flex-col items-start gap-3 border-t border-neutral-border/40 pt-6 md:flex-row md:items-center md:justify-between md:gap-4">
            <div className="flex flex-col gap-1">
                <h3 className="text-base font-semibold text-black">회원 탈퇴</h3>
                <p className="text-sm text-neutral-border">탈퇴하면 진단 기록이 모두 삭제되고 복구할 수 없어요.</p>
            </div>
            <button
                type="button"
                onClick={handleWithdraw}
                disabled={isPending}
                className="shrink-0 cursor-pointer text-sm font-medium text-neutral-border underline underline-offset-2 hover:text-status-danger disabled:cursor-default disabled:opacity-50"
            >
                {isPending ? "탈퇴 중" : "탈퇴하기"}
            </button>
        </div>
    );
}

export default WithdrawSection;
