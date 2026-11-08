import { Outlet } from 'react-router-dom'

import Header from '@/components/common/Header'

function Layout() {
    return (
        <>
            <Header />
            <main className="flex justify-center mx-auto mt-22.25 mb-12 w-full px-5 max-w-297 md:mt-40 md:mb-40 md:w-3/5 md:min-w-150 md:px-0">
                <Outlet />
            </main>
        </>
    );
}

export default Layout;
