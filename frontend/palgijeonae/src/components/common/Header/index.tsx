import { useAuthStore } from '../../../store/useAuthStore'
import logo from '../../../assets/logo.png'

function Header() {
    // const isLoggedIn = useAuthStore((state) => state.isLoggedIn)
    const isLoggedIn = true

    return (
        <header>
            <img src={logo} alt="Logo" />
            {isLoggedIn ? (
                <button>마이페이지</button>
            ) : (
                <button>로그인</button>
            )}
        </header>
    );
}

export default Header;
