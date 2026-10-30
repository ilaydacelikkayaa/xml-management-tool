function Sidebar({ activePage, setActivePage }) {
    return (
        <aside className="sidebar">
            <h2 className="sidebar-title">XML Manager</h2>

            <nav className="sidebar-nav">
                <button
                    type="button"
                    className={`nav-item ${activePage === 'dashboard' ? 'active' : ''}`}
                    onClick={() => setActivePage('dashboard')}
                >
                    Dashboard
                </button>

                <button
                    type="button"
                    className={`nav-item ${activePage === 'fields' ? 'active' : ''}`}
                    onClick={() => setActivePage('fields')}
                >
                    XML Fields
                </button>

                <button
                    type="button"
                    className={`nav-item ${activePage === 'globalLists' ? 'active' : ''}`}
                    onClick={() => setActivePage('globalLists')}
                >
                    GlobalLists
                </button>
                <button
                    type="button"
                    className={`nav-item ${activePage === 'azure' ? 'active' : ''}`}
                    onClick={() => setActivePage('azure')}
                >
                    Azure Repos
                </button>
            </nav>

        </aside>
    )
}

export default Sidebar