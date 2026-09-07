import { useNavigate } from 'react-router-dom'

import { useAuthStore } from '../../../store/useAuthStore'
import logo from '../../../assets/logo.png'

function Header() {
    // const isLoggedIn = useAuthStore((state) => state.isLoggedIn)
    const isLoggedIn = true
    const navigate = useNavigate()

    const handleLogoClick = () => {
        navigate('/')
    }

    const handleButtonClick = () => {
        navigate(isLoggedIn ? '/mypage' : '/login')
    }

    return (
        <header className="fixed top-0 left-0 z-50 flex w-full items-center justify-between border-b border-neutral-border bg-white px-5 py-4">
            <img src={logo} 
                alt="Logo" 
                className="cursor-pointer w-[150px] object-contain" 
                onClick={handleLogoClick} />
            <button
                className="flex cursor-pointer items-center justify-center rounded-full border border-neutral-border px-8 py-2 text-base font-medium text-neutral-dark"
                onClick={handleButtonClick}
            >
                {isLoggedIn ? '마이페이지' : '로그인'}
            </button>
        </header>
    );
}

export default Header;
