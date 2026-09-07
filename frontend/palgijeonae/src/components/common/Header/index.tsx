import { useAuthStore } from '../../../store/useAuthStore'
import logo from '../../../assets/logo.png'

function Header() {
    // const isLoggedIn = useAuthStore((state) => state.isLoggedIn)
    const isLoggedIn = true

    return (
        <header className="fixed top-0 left-0 z-50 flex w-full items-center justify-between border-b border-neutral-border bg-white px-5 py-4">
            <img src={logo} alt="Logo" className="w-[150px] object-contain" />
            <button className="flex items-center justify-center rounded-full border border-neutral-border px-8 py-2 text-l font-medium text-neutral-dark">
                {isLoggedIn ? '마이페이지' : '로그인'}
            </button>
        </header>
    );
}

export default Header;
