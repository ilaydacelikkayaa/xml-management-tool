
import { useEffect, useState } from 'react'

const INITIAL_BRANCH = 'refactor/local-witadmin'

function GitHubHistory() {
    const [branch, setBranch] = useState(INITIAL_BRANCH)
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

    useEffect(() => {
        let cancelled = false

        async function loadXmlFiles() {
            setLoading(true)
            setError('')
            setXmlFiles([])
            setSelectedFile('')
            setHistory([])
            setSelectedCommit('')
            setCommitDiff(null)

            try {
                const params = new URLSearchParams({ branch })
                const response = await fetch(
                    `/github/xml-files?${params.toString()}`,
                    { cache: 'no-store' }
                )
                const data = await response.json()

                if (!response.ok) {
                    throw new Error(data.detail || 'XML files could not be loaded.')
                }

                if (!cancelled) {
                    const files = data.files || []
                    setXmlFiles(files)
                    setSelectedFile(files[0] || '')
                }
            } catch (err) {
                if (!cancelled) setError(err.message)
            } finally {
                if (!cancelled) setLoading(false)
            }
        }

        if (branch.trim()) loadXmlFiles()

        return () => { cancelled = true }
    }, [branch])

    function changeFile(file) {
        setSelectedFile(file)
        setHistory([])
        setHistoryError('')
        setSelectedCommit('')
        setCommitDiff(null)
        setDiffError('')
    }

    async function loadHistory() {
        if (!selectedFile) return

        const file = selectedFile
        setHistoryLoading(true)
        setHistoryError('')
        setHistory([])
        setSelectedCommit('')
        setCommitDiff(null)

        try {
            const params = new URLSearchParams({
                file_path: file,
                branch,
            })

            const response = await fetch(
                `/github/xml-history?${params.toString()}`,
                { cache: 'no-store' }
            )
            const data = await response.json()

            if (!response.ok) {
                throw new Error(data.detail || 'History could not be loaded.')
            }

            setHistory(data.history || [])
        } catch (err) {
            setHistoryError(err.message)
        } finally {
            setHistoryLoading(false)
        }
    }

    async function loadCommitDiff(commitSha) {
        if (!selectedFile) return

        setSelectedCommit(commitSha)
        setCommitDiff(null)
        setDiffError('')
        setDiffLoading(true)

        try {
            const params = new URLSearchParams({
                file_path: selectedFile,
                commit_sha: commitSha,
            })

            const response = await fetch(
                `/github/xml-commit-diff?${params.toString()}`,
                { cache: 'no-store' }
            )
            const data = await response.json()

            if (!response.ok) {
                throw new Error(data.detail || 'Commit diff could not be loaded.')
            }

            setCommitDiff(data)
        } catch (err) {
            setDiffError(err.message)
        } finally {
            setDiffLoading(false)
        }
    }

    function formatDate(date) {
        return date
            ? new Date(date).toLocaleString('tr-TR')
            : 'Unknown date'
    }

    function renderDiff(patch) {
        if (!patch) {
            return <p className="gh-empty">No text diff available.</p>
        }

        return (
            <div className="gh-diff-code">
                {patch.split('\n').map((line, index) => {
                    let kind = 'context'

                    if (line.startsWith('+') && !line.startsWith('+++')) {
                        kind = 'added'
                    } else if (line.startsWith('-') && !line.startsWith('---')) {
                        kind = 'removed'
                    } else if (line.startsWith('@@')) {
                        kind = 'header'
                    }

                    return (
                        <div key={index} className={`gh-diff-line gh-${kind}`}>
                            {line || ' '}
                        </div>
                    )
                })}
            </div>
        )
    }

    return (
        <section className="github-history-page">
            <div className="gh-page-header">
                <div>
                    <p className="breadcrumb">MANAGEMENT / VERSION CONTROL</p>
                    <h1>GitHub Version Control</h1>
                    <p>Manage XML backups and track configuration changes.</p>
                </div>
                <div className="gh-header-icon">⌘</div>
            </div>

            <div className="gh-card gh-selection-card">
                <div className="gh-card-heading">
                    <div>
                        <h2>Repository Explorer</h2>
                        <p>Select a branch and an XML definition to inspect.</p>
                    </div>
                    <span className="gh-chip">GitHub Connected</span>
                </div>

                <div className="gh-selection-grid">
                    <div className="gh-field">
                        <label htmlFor="gh-branch">Branch</label>
                        <input
                            id="gh-branch"
                            value={branch}
                            onChange={(event) => setBranch(event.target.value)}
                        />
                    </div>

                    <div className="gh-field">
                        <label htmlFor="gh-file">XML Definition</label>
                        <select
                            id="gh-file"
                            value={selectedFile}
                            onChange={(event) => changeFile(event.target.value)}
                            disabled={loading || !xmlFiles.length}
                        >
                            {!xmlFiles.length && (
                                <option value="">No XML files available</option>
                            )}
                            {xmlFiles.map((file) => (
                                <option key={file} value={file}>
                                    {file}
                                </option>
                            ))}
                        </select>
                    </div>
                </div>

                {loading && <p className="gh-muted">Loading XML files...</p>}
                {error && <p className="gh-error" role="alert">{error}</p>}

                {!loading && !error && (
                    <div className="gh-selection-footer">
                        <span>{xmlFiles.length} XML file(s) found</span>
                        <button
                            className="gh-primary-btn"
                            type="button"
                            onClick={loadHistory}
                            disabled={!selectedFile || historyLoading}
                        >
                            {historyLoading ? 'Loading...' : 'Load Version History'}
                        </button>
                    </div>
                )}
            </div>

            <div className="gh-content-grid">
                <div className="gh-card gh-history-card">
                    <div className="gh-card-heading">
                        <div>
                            <h2>Version History</h2>
                            <p>Commits for the selected XML file.</p>
                        </div>
                        <span className="gh-count">{history.length}</span>
                    </div>

                    {historyError && (
                        <p className="gh-error" role="alert">{historyError}</p>
                    )}

                    {historyLoading && (
                        <p className="gh-muted">Loading commits...</p>
                    )}

                    {!historyLoading && history.length === 0 && (
                        <div className="gh-empty">
                            Select an XML file and load its version history.
                        </div>
                    )}

                    <div className="gh-commit-list">
                        {history.map((commit) => (
                            <button
                                key={commit.sha}
                                type="button"
                                className={`gh-commit ${selectedCommit === commit.sha ? 'selected' : ''
                                    }`}
                                onClick={() => loadCommitDiff(commit.sha)}
                            >
                                <span className="gh-commit-dot" />
                                <span className="gh-commit-body">
                                    <strong>{commit.message}</strong>
                                    <span className="gh-commit-meta">
                                        {commit.sha.slice(0, 7)} · {commit.author}
                                    </span>
                                    <span className="gh-commit-date">
                                        {formatDate(commit.date)}
                                    </span>
                                </span>
                            </button>
                        ))}
                    </div>
                </div>

                <div className="gh-card gh-changes-card">
                    <div className="gh-card-heading">
                        <div>
                            <h2>Commit Changes</h2>
                            <p>Review additions and deletions.</p>
                        </div>
                    </div>

                    {!selectedCommit && (
                        <div className="gh-empty">
                            Select a commit from the history to view changes.
                        </div>
                    )}

                    {diffLoading && (
                        <p className="gh-muted">Loading changes...</p>
                    )}

                    {diffError && (
                        <p className="gh-error" role="alert">{diffError}</p>
                    )}

                    {commitDiff && (
                        <>
                            <div className="gh-diff-summary">
                                <div>
                                    <span className="gh-summary-label">COMMIT</span>
                                    <strong>{commitDiff.commit_sha.slice(0, 7)}</strong>
                                </div>
                                <span className="gh-added-count">
                                    +{commitDiff.additions} added
                                </span>
                                <span className="gh-removed-count">
                                    -{commitDiff.deletions} removed
                                </span>
                            </div>

                            {renderDiff(commitDiff.patch)}

                            {commitDiff.commit_url && (
                                <a
                                    className="gh-commit-link"
                                    href={commitDiff.commit_url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                >
                                    View commit on GitHub ↗
                                </a>
                            )}
                        </>
                    )}
                </div>
            </div>
        </section>
    )
}

export default GitHubHistory
