import type { Location } from "react-router-dom";

/** 화면을 이동할 때 location.state에 담아 보내는 값. 도착한 화면의 "이전으로" 버튼이 히스토리를 되돌릴 수 있는지 판단하는 데 쓴다. */
export interface FromState {
    from: string
}

/** 현재 화면의 경로(쿼리 포함)를 다음 화면으로 넘기는 state를 만든다. */
export function createFromState({ pathname, search }: Pick<Location, "pathname" | "search">): FromState {
    return { from: pathname + search };
}

/** location.state가 createFromState로 만든 값인지 확인한다. 직접 주소를 입력하거나 새 탭으로 열면 state가 없다. */
export function hasFromState(state: unknown): state is FromState {
    return typeof state === "object" && state !== null && typeof (state as { from?: unknown }).from === "string";
}
