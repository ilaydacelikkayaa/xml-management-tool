import { useEffect, useState } from 'react'

const INITIAL_COLLECTION = ''
const INITIAL_PROJECT = ''

async function getJson(url, signal) {
    const response = await fetch(url, { cache: 'no-store', signal })
    const data = await response.json()
    if (!response.ok) {
        const detail = data.detail
        throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail || data))
    }
    return data
}

function paramsOf(values) {
    return new URLSearchParams(values).toString()
}

function normalizeFiles(data) {
    const items = Array.isArray(data) ? data : (data.files || data.items || [])
    return items.map(item => typeof item === 'string' ? item : (item.path || item.file_path || item.gitPath)).filter(Boolean)
}

function normalizeHistory(data) {
    const items = Array.isArray(data) ? data : (data.history || data.commits || data.value || [])
    return items.map(item => ({
        id: item.commit_id || item.commitId || item.sha || item.id || '',
        message: item.message || item.comment || 'XML commit',
        author: typeof item.author === 'string' ? item.author : (item.author?.name || item.author?.displayName || 'Unknown'),
        date: item.date || item.timestamp || item.author?.date || item.committer?.date || '',
    })).filter(item => item.id)
}

function AzureReposHistory() {
    const [collection, setCollection] = useState(INITIAL_COLLECTION)
    const [project, setProject] = useState(INITIAL_PROJECT)
    const [repositories, setRepositories] = useState([])
    const [repositoryId, setRepositoryId] = useState('')
    const [repositoryLoading, setRepositoryLoading] = useState(false)
    const [repositoryError, setRepositoryError] = useState('')
    const [branch, setBranch] = useState('')
    const [xmlFiles, setXmlFiles] = useState([])
    const [selectedFile, setSelectedFile] = useState('')
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState('')
    const [history, setHistory] = useState([])
    const [historyLoading, setHistoryLoading] = useState(false)
    const [historyError, setHistoryError] = useState('')
    const [selectedCommit, setSelectedCommit] = useState('')
    const [commitDiff, setCommitDiff] = useState(null)
    const [diffLoading, setDiffLoading] = useState(false)
    const [diffError, setDiffError] = useState('')
    const [collections, setCollections] = useState([])
    const [projects, setProjects] = useState([])
    useEffect(() => {
        fetch('/collections')
            .then(res => res.json())
            .then(data => {
                console.log('Collections:', data)
                setCollections(data)
            })
            .catch(console.error)
    }, [])
    useEffect(() => {
        const controller = new AbortController()
        setRepositories([])
        setRepositoryId('')
        setBranch('')
        setRepositoryError('')
        if (!collection.trim() || !project.trim()) return () => controller.abort()
        async function loadRepositories() {
            setRepositoryLoading(true)
            try {
                const data = await getJson(`/azure-repos/repositories?${paramsOf({ collection_name: collection.trim(), project_name: project.trim() })}`, controller.signal)
                const repos = Array.isArray(data) ? data : (data.repositories || data.value || [])
                if (!controller.signal.aborted) {
                    setRepositories(repos)
                    if (repos.length === 1) setRepositoryId(repos[0].id)
                }
            } catch (err) {
                if (!controller.signal.aborted) setRepositoryError(err.message)
            } finally {
                if (!controller.signal.aborted) setRepositoryLoading(false)
            }
        }
        loadRepositories()
        return () => controller.abort()
    }, [collection, project])
    useEffect(() => {
        setProjects([])
        setProject('')

        if (!collection) return

        const controller = new AbortController()

        async function loadProjects() {
            try {
                const data = await getJson(
                    `/projects?collection_name=${encodeURIComponent(collection)}`,
                    controller.signal
                )

                const items = Array.isArray(data)
                    ? data
                    : data.projects || data.value || []

                setProjects(items.map(item =>
                    typeof item === 'string' ? item : item.name
                ))
            } catch (err) {
                if (!controller.signal.aborted) console.error(err)
            }
        }

        loadProjects()
        return () => controller.abort()
    }, [collection])
    useEffect(() => {
        const repo = repositories.find(item => item.id === repositoryId)
        setBranch(repo?.default_branch?.split('refs/heads/').pop() || '')
    }, [repositoryId, repositories])

    useEffect(() => {
        const controller = new AbortController()
        setXmlFiles([])
        setSelectedFile('')
        setHistory([])
        setHistoryError('')
        setSelectedCommit('')
        setCommitDiff(null)
        setError('')
        if (!collection.trim() || !project.trim() || !repositoryId || !branch.trim()) return () => controller.abort()
        async function loadFiles() {
            setLoading(true)
            try {
                const query = paramsOf({ collection_name: collection.trim(), project_name: project.trim(), repository_id: repositoryId, branch: branch.trim() })
                const data = await getJson(`/azure-repos/xml-files?${query}`, controller.signal)
                if (!controller.signal.aborted) {
                    const files = normalizeFiles(data)
                    setXmlFiles(files)
                    setSelectedFile(files[0] || '')
                }
            } catch (err) {
                if (!controller.signal.aborted) setError(err.message)
            } finally {
                if (!controller.signal.aborted) setLoading(false)
            }
        }
        loadFiles()
        return () => controller.abort()
    }, [collection, project, repositoryId, branch])

    function changeFile(file) {
        setSelectedFile(file)
        setHistory([])
        setHistoryError('')
        setSelectedCommit('')
        setCommitDiff(null)
        setDiffError('')
    }

    async function loadHistory() {
        if (!selectedFile || !repositoryId) return
        setHistoryLoading(true)
        setHistoryError('')
        setHistory([])
        setSelectedCommit('')
        setCommitDiff(null)
        try {
            const query = paramsOf({ collection_name: collection.trim(), project_name: project.trim(), repository_id: repositoryId, file_path: selectedFile, branch: branch.trim() })
            const data = await getJson(`/azure-repos/xml-history?${query}`)
            setHistory(normalizeHistory(data))
        } catch (err) {
            setHistoryError(err.message)
        } finally {
            setHistoryLoading(false)
        }
    }

    async function loadCommitDiff(commitId) {
        if (!selectedFile || !repositoryId) return
        setSelectedCommit(commitId)
        setCommitDiff(null)
        setDiffError('')
        setDiffLoading(true)
        try {
            const query = paramsOf({ collection_name: collection.trim(), project_name: project.trim(), repository_id: repositoryId, file_path: selectedFile, commit_id: commitId })
            const data = await getJson(`/azure-repos/xml-commit-diff?${query}`)
            setCommitDiff(data)
        } catch (err) {
            setDiffError(err.message)
        } finally {
            setDiffLoading(false)
        }
    }

    function renderDiff(patch) {
        if (!patch) return <p className="gh-empty">No text diff available.</p>
        return (
            <div className="gh-diff-code">
                {patch.split('\n').map((line, index) => {
                    let kind = 'context'
                    if (line.startsWith('+') && !line.startsWith('+++')) kind = 'added'
                    else if (line.startsWith('-') && !line.startsWith('---')) kind = 'removed'
                    else if (line.startsWith('@@')) kind = 'header'
                    return <div key={index} className={`gh-diff-line gh-${kind}`}>{line || ' '}</div>
                })}
            </div>
        )
    }

    const patch = commitDiff?.diff ?? commitDiff?.patch ?? ''
    const additions = commitDiff?.added_lines ?? commitDiff?.additions ?? 0
    const deletions = commitDiff?.removed_lines ?? commitDiff?.deletions ?? 0

    return (
        <section className="github-history-page">
            <div className="gh-page-header">
                <div>
                    <p className="breadcrumb">MANAGEMENT / VERSION CONTROL</p>
                    <h1>Azure Repos Version Control</h1>
                    <p>Manage XML backups and track configuration changes.</p>
                </div>
                <div className="gh-header-icon">⌘</div>
            </div>

            <div className="gh-card gh-selection-card">
                <div className="gh-card-heading">
                    <div>
                        <h2>Repository Explorer</h2>
                        <p>Select a collection, project, repository, branch and XML definition.</p>
                    </div>
                    <span className="gh-chip">Azure Repos</span>
                </div>

                <div className="gh-selection-grid">
                    <div className="gh-field">
                        <label htmlFor="az-collection">Collection</label>
                        <select
                            id="az-collection"
                            value={collection}
                            onChange={event => setCollection(event.target.value)}
                        >
                            <option value="">Select Collection</option>
                            {collections.map(item => (
                                <option key={item} value={item}>{item}</option>
                            ))}
                        </select>
                    </div>
                    <div className="gh-field">
                        <label htmlFor="az-project">Project</label>
                        <select
                            id="az-project"
                            value={project}
                            onChange={event => setProject(event.target.value)}
                            disabled={!collection}
                        >
                            <option value="">Select Project</option>
                            {projects.map(item => (
                                <option key={item} value={item}>{item}</option>
                            ))}
                        </select>                    </div>
                    <div className="gh-field">
                        <label htmlFor="az-repository">Repository</label>
                        <select id="az-repository" value={repositoryId} onChange={event => setRepositoryId(event.target.value)} disabled={repositoryLoading || !repositories.length}>
                            <option value="">{repositoryLoading ? 'Loading repositories...' : 'Select repository'}</option>
                            {repositories.map(repo => <option key={repo.id} value={repo.id}>{repo.name}</option>)}
                        </select>
                    </div>
                    <div className="gh-field">
                        <label htmlFor="az-branch">Branch</label>
                        <select
                            id="az-branch"
                            value={branch}
                            onChange={event => setBranch(event.target.value)}
                            disabled={!repositoryId}
                        >
                            <option value="">Select Branch</option>
                            {branch && <option value={branch}>{branch}</option>}
                        </select>                    </div>
                    <div className="gh-field">
                        <label htmlFor="az-file">XML Definition</label>
                        <select id="az-file" value={selectedFile} onChange={event => changeFile(event.target.value)} disabled={loading || !xmlFiles.length}>
                            {!xmlFiles.length && <option value="">No XML files available</option>}
                            {xmlFiles.map(file => <option key={file} value={file}>{file}</option>)}
                        </select>
                    </div>
                </div>
                {repositoryError && <p className="gh-error" role="alert">{repositoryError}</p>}
                {loading && <p className="gh-muted">Loading XML files...</p>}
                {error && <p className="gh-error" role="alert">{error}</p>}
                <div className="gh-selection-footer">
                    <span>{xmlFiles.length} XML file(s) found</span>
                    <button className="gh-primary-btn" type="button" onClick={loadHistory} disabled={!selectedFile || historyLoading}>
                        {historyLoading ? 'Loading...' : 'Load Version History'}
                    </button>
                </div>
            </div>

            <div className="gh-content-grid">
                <div className="gh-card gh-history-card">
                    <div className="gh-card-heading">
                        <div><h2>Version History</h2><p>Commits for the selected XML file.</p></div>
                        <span className="gh-count">{history.length}</span>
                    </div>
                    {historyError && <p className="gh-error" role="alert">{historyError}</p>}
                    {historyLoading && <p className="gh-muted">Loading commits...</p>}
                    {!historyLoading && !history.length && <div className="gh-empty">Select an XML file and load its version history.</div>}
                    <div className="gh-commit-list">
                        {history.map(commit => (
                            <button key={commit.id} type="button" className={`gh-commit ${selectedCommit === commit.id ? 'selected' : ''}`} onClick={() => loadCommitDiff(commit.id)}>
                                <span className="gh-commit-dot" />
                                <span className="gh-commit-body">
                                    <strong>{commit.message}</strong>
                                    <span className="gh-commit-meta">{commit.id.slice(0, 7)} · {commit.author}</span>
                                    <span className="gh-commit-date">{commit.date ? new Date(commit.date).toLocaleString('tr-TR') : 'Unknown date'}</span>
                                </span>
                            </button>
                        ))}
                    </div>
                </div>

                <div className="gh-card gh-changes-card">
                    <div className="gh-card-heading"><div><h2>Commit Changes</h2><p>Review additions and deletions.</p></div></div>
                    {!selectedCommit && <div className="gh-empty">Select a commit from the history to view changes.</div>}
                    {diffLoading && <p className="gh-muted">Loading changes...</p>}
                    {diffError && <p className="gh-error" role="alert">{diffError}</p>}
                    {commitDiff && <>
                        <div className="gh-diff-summary">
                            <div><span className="gh-summary-label">COMMIT</span><strong>{selectedCommit.slice(0, 7)}</strong></div>
                            <span className="gh-added-count">+{additions} added</span>
                            <span className="gh-removed-count">-{deletions} removed</span>
                        </div>
                        {renderDiff(patch)}
                    </>}
                </div>
            </div>
        </section>
    )
}

export default AzureReposHistory
