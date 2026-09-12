import { Outlet } from 'react-router-dom'

import Header from '../common/Header'

function Layout() {
    return (
        <>
            <Header />
            <main className="flex justify-center mx-auto mt-40 w-3/5 min-w-150 max-w-297">
                <Outlet />
            </main>
        </>
    );
}

export default Layout;
