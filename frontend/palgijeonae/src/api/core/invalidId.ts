import axios from "axios";

// 진단서·상품 id로 조회했을 때 "유효하지 않은 id"로 안내해야 하는 오류인지 판단한다.
// BE가 id를 UUID로 받아서, 형식이 다르면 400, 형식은 맞는데 없으면 404를 돌려준다. 사용자에게는 둘 다 같은 상황이다.
export function isInvalidIdError(error: unknown): boolean {
    if (!axios.isAxiosError(error)) {
        return false;
    }

    const status = error.response?.status;
    return status === 400 || status === 404;
}
