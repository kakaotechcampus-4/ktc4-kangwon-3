import { Outlet } from 'react-router-dom'

import Header from '../common/Header'

function Layout() {
    return (
        <>
            <Header />
            <main className="mx-auto mt-40 w-3/5">
                <Outlet />
            </main>
        </>
    );
}

export default Layout;
