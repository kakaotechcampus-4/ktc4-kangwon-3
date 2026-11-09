import { Outlet } from 'react-router-dom'

import Footer from '@/components/common/Footer'
import Header from '@/components/common/Header'

function Layout() {
    return (
        // 본문이 짧은 페이지에서도 푸터가 화면 아래에 붙도록 본문을 남는 높이만큼 늘린다.
        <div className="flex min-h-screen flex-col">
            <Header />
            <main className="flex flex-1 items-start justify-center mx-auto mt-22.25 mb-16 w-full px-5 max-w-297 md:mt-40 md:mb-40 md:w-3/5 md:min-w-150 md:px-0">
                <Outlet />
            </main>
            <Footer />
        </div>
    );
}

export default Layout;
