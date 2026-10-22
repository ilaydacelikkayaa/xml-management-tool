import { useState, useEffect } from 'react'
import Sidebar from './components/Sidebar'
import './App.css'
import XmlFields from './components/XmlFields'
import GlobalLists from './components/GlobalLists'

function App() {
  const [activePage, setActivePage] = useState('dashboard')
  const [collections, setCollections] = useState([])
  const [selectedCollection, setSelectedCollection] = useState('')
  const [collectionsLoading, setCollectionsLoading] = useState(true)

  const [stats, setStats] = useState({
    projects: null,
    globalLists: null,
    listItems: null,
  })
  const [statsLoading, setStatsLoading] = useState(true)
  const [statsError, setStatsError] = useState('')

  // 1. Collection listesini yükle
  useEffect(() => {
    let cancelled = false

    async function loadCollections() {
      setCollectionsLoading(true)
      setStatsError('')

      try {
        const response = await fetch('/collections')

        if (!response.ok) {
          throw new Error('Collections could not be loaded.')
        }

        const data = await response.json()

        if (!Array.isArray(data)) {
          throw new Error('Unexpected collections response.')
        }

        if (cancelled) return

        setCollections(data)

        setSelectedCollection((current) => {
          if (data.includes(current)) return current
          if (data.includes('XMLLabCollection')) {
            return 'XMLLabCollection'
          }
          return data[0] ?? ''
        })
      } catch (err) {
        if (!cancelled) {
          setStatsError(err.message)
        }
      } finally {
        if (!cancelled) {
          setCollectionsLoading(false)
        }
      }
    }

    loadCollections()

    return () => {
      cancelled = true
    }
  }, [])

  // 2. Seçilen collection için istatistikleri yükle
  useEffect(() => {
    if (!selectedCollection) return

    let cancelled = false

    async function loadDashboardStats() {
      setStatsLoading(true)
      setStatsError('')
      setStats({
        projects: null,
        globalLists: null,
        listItems: null,
      })

      try {
        const [projectsResult, listsResult] = await Promise.allSettled([
          fetch(
            `/projects?collection_name=${encodeURIComponent(selectedCollection)}`
          ).then(async (response) => {
            if (!response.ok) {
              throw new Error('Projects could not be loaded.')
            }
            return response.json()
          }),

          fetch(
            `/global-lists?collection_name=${encodeURIComponent(selectedCollection)}`
          ).then(async (response) => {
            if (!response.ok) {
              throw new Error('GlobalLists could not be loaded.')
            }
            return response.json()
          }),
        ])

        if (cancelled) return

        let projects = null
        let globalLists = null
        let listItems = null

        if (projectsResult.status === 'fulfilled') {
          const data = projectsResult.value
          const projectArray = Array.isArray(data.value)
            ? data.value
            : Array.isArray(data.projects)
              ? data.projects
              : Array.isArray(data)
                ? data
                : null

          if (projectArray) {
            projects = projectArray.length
          }
        }

        if (listsResult.status === 'fulfilled') {
          const data = listsResult.value

          if (data.success && Array.isArray(data.global_lists)) {
            globalLists = data.global_lists.length
            listItems = data.global_lists.reduce(
              (total, list) => total + (list.values?.length ?? 0),
              0
            )
          }
        }

        setStats({ projects, globalLists, listItems })

        if (projects === null || globalLists === null) {
          setStatsError(
            'Some statistics could not be loaded for this collection.'
          )
        }
      } catch {
        if (!cancelled) {
          setStatsError('Dashboard statistics could not be loaded.')
        }
      } finally {
        if (!cancelled) {
          setStatsLoading(false)
        }
      }
    }

    loadDashboardStats()

    return () => {
      cancelled = true
    }
  }, [selectedCollection])



  return (
    <div className="app-layout">
      <Sidebar
        activePage={activePage}
        setActivePage={setActivePage}
      />

      <main className="main-content">
        {activePage === 'dashboard' && (
          <div className="dashboard">
            <p className="breadcrumb">MANAGEMENT / OVERVIEW</p>

            <div className="dashboard-header">
              <h1>Dashboard</h1>
              <p>
                Manage Azure DevOps XML configurations
                through a centralized interface.
              </p>
            </div>


            <section className="dashboard-section">
              <div className="dashboard-overview-header">
                <div className="section-heading">
                  <h2>System Overview</h2>
                  <p>Azure DevOps configuration overview.</p>
                </div>

                <div className="dashboard-collection-filter">
                  <label htmlFor="dashboard-collection">
                    Active Collection
                  </label>

                  <div className="dashboard-collection-select">
                    <span className="collection-select-icon">▦</span>

                    <select
                      id="dashboard-collection"
                      value={selectedCollection}
                      onChange={(event) =>
                        setSelectedCollection(event.target.value)
                      }
                      disabled={
                        collectionsLoading || collections.length === 0
                      }
                    >
                      {collections.map((collection) => (
                        <option key={collection} value={collection}>
                          {collection}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
              </div>

              {statsError && (
                <p className="dashboard-stats-error" role="status">
                  {statsError}
                </p>
              )}

              <div className="dashboard-stats-grid">
                <article className="dashboard-stat-card">
                  <div className="dashboard-stat-top">
                    <span className="dashboard-stat-icon projects-icon">▦</span>
                    <span className="dashboard-stat-label">PROJECTS</span>
                  </div>
                  <strong className="dashboard-stat-value">
                    {statsLoading ? '—' : stats.projects ?? 'N/A'}
                  </strong>
                  <p>Projects in {selectedCollection || 'selected collection'}</p>                </article>

                <article className="dashboard-stat-card">
                  <div className="dashboard-stat-top">
                    <span className="dashboard-stat-icon lists-icon">☷</span>
                    <span className="dashboard-stat-label">GLOBALLISTS</span>
                  </div>
                  <strong className="dashboard-stat-value">
                    {statsLoading ? '—' : stats.globalLists ?? 'N/A'}
                  </strong>
                  <p>Available shared lists</p>
                </article>

                <article className="dashboard-stat-card">
                  <div className="dashboard-stat-top">
                    <span className="dashboard-stat-icon items-icon">≡</span>
                    <span className="dashboard-stat-label">LIST ITEMS</span>
                  </div>
                  <strong className="dashboard-stat-value">
                    {statsLoading ? '—' : stats.listItems ?? 'N/A'}
                  </strong>
                  <p>Total values across GlobalLists</p>
                </article>
              </div>
            </section>


            <section className="dashboard-section">
              <div className="section-heading">
                <h2>Quick Actions</h2>
                <p>Access frequently used management tools.</p>
              </div>

              <div className="dashboard-cards">
                <button
                  type="button"
                  className="dashboard-card"
                  onClick={() => setActivePage('fields')}
                >
                  <span className="card-icon">⌘</span>
                  <h3>Manage XML Fields →</h3>
                  <p>
                    Add, update and manage Work Item Type fields.
                  </p>
                </button>

                <button
                  type="button"
                  className="dashboard-card"
                  onClick={() => setActivePage('globalLists')}
                >
                  <span className="card-icon">☷</span>
                  <h3>Manage Global Lists →</h3>
                  <p>
                    Manage shared GlobalList items and configurations.
                  </p>
                </button>
              </div>
            </section>

            <section className="dashboard-section">
              <div className="section-heading">
                <h2>Management Capabilities</h2>
                <p>Core features of the XML Management Tool.</p>
              </div>
              <div className="capability-grid">
                <div className="capability-card">
                  <span className="capability-icon">▦</span>
                  <h3>Multi-Project Management</h3>
                  <p>
                    Manage XML field configurations across
                    multiple Azure DevOps projects.
                  </p>
                </div>

                <div className="capability-card">
                  <span className="capability-icon">≡</span>
                  <h3>XML Comparison</h3>
                  <p>
                    Compare original and modified XML
                    configurations before import.
                  </p>
                </div>

                <div className="capability-card">
                  <span className="capability-icon">▣</span>
                  <h3>Backup Protection</h3>
                  <p>
                    Preserve original XML configurations
                    before applying changes.
                  </p>
                </div>

                <div className="capability-card">
                  <span className="capability-icon">✓</span>
                  <h3>Preflight Validation</h3>
                  <p>
                    Verify preview integrity and configuration
                    readiness before import.
                  </p>
                </div>
              </div>
            </section>

            <section className="dashboard-section">
              <div className="workflow-panel">
                <h2>Safe Configuration Workflow</h2>
                <p>
                  Configuration changes follow a controlled process
                  designed to reduce unintended modifications.
                </p>

                <div className="workflow-steps">
                  <div className="workflow-step">
                    <span className="step-number">01</span>
                    <strong>Select</strong>
                    <small>Choose projects and operation</small>
                  </div>

                  <span className="workflow-arrow">→</span>

                  <div className="workflow-step">
                    <span className="step-number">02</span>
                    <strong>Preview</strong>
                    <small>Review XML changes</small>
                  </div>

                  <span className="workflow-arrow">→</span>

                  <div className="workflow-step">
                    <span className="step-number">03</span>
                    <strong>Validate</strong>
                    <small>Run preflight checks</small>
                  </div>

                  <span className="workflow-arrow">→</span>

                  <div className="workflow-step">
                    <span className="step-number">04</span>
                    <strong>Apply</strong>
                    <small>Backup and import</small>
                  </div>
                </div>
              </div>
            </section>
          </div>
        )}

        {activePage === 'fields' && (
          <XmlFields selectedCollection={selectedCollection} />
        )}

        {activePage === 'globalLists' && (
          <GlobalLists selectedCollection={selectedCollection} />
        )}
      </main>
    </div>
  )
}

export default App

