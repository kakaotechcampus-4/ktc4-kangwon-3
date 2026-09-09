import { Outlet } from 'react-router-dom'

import Header from '../common/Header'

function Layout() {
    return (
        <>
            <Header />
            <main className="flex mx-auto mt-40 w-3/5 justify-center">
                <Outlet />
            </main>
        </>
    );
}

export default Layout;
