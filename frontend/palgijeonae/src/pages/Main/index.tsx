import { useAuthStore } from "../../store/useAuthStore.ts"

function MainPage() {
    // const isLoggedIn = useAuthStore((state) => state.isLoggedIn);
    const isLoggedIn = true

    return (
        <div>
            <h1>메인 페이지 입니다.</h1>
        </div>
    );
}

export default MainPage;