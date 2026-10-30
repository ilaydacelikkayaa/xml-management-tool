
import { useEffect, useState } from 'react'

function GarbageCleanup({ selectedCollection, onReviewField }) {
    const [collections, setCollections] = useState([])

    const [collectionName, setCollectionName] = useState(selectedCollection || '')
    const [projects, setProjects] = useState([])
    const [projectName, setProjectName] = useState('')
    const [multiProjectMode, setMultiProjectMode] = useState(false)
    const [multiPreviewResult, setMultiPreviewResult] = useState(null)
    const [selectedProjects, setSelectedProjects] = useState([])
    const [availableWits, setAvailableWits] = useState([])
    const [selectedWit, setSelectedWit] = useState('')
    const [startDate, setStartDate] = useState('')
    const [loading, setLoading] = useState(false)
    const [optionsLoading, setOptionsLoading] = useState(false)
    const [error, setError] = useState('')
    const [result, setResult] = useState(null)
    const [searchTerm, setSearchTerm] = useState('')
    const [candidateOnly, setCandidateOnly] = useState(false)
    const [selectedFields, setSelectedFields] = useState([])
    const [bulkLoading, setBulkLoading] = useState(false)
    const [bulkResult, setBulkResult] = useState(null)
    const [bulkError, setBulkError] = useState('')
    const [showSystemWarning, setShowSystemWarning] = useState(false)
    const [checkResult, setCheckResult] = useState(null)
    const [checkError, setCheckError] = useState('')
    const [checkLoading, setCheckLoading] = useState(false)

    const [showApplyConfirm, setShowApplyConfirm] = useState(false)
    const [applyLoading, setApplyLoading] = useState(false)
    const [applyError, setApplyError] = useState('')
    const [applyResult, setApplyResult] = useState(null)
    const [multiAnalysisResult, setMultiAnalysisResult] = useState(null)
    useEffect(() => {
        let cancelled = false

        async function loadCollections() {
            try {
                const response = await fetch('/api/collections')
                if (!response.ok) throw new Error('Collections could not be loaded.')

                const data = await response.json()
                if (!cancelled) {
                    const items = Array.isArray(data) ? data : []
                    setCollections(items)
                    setCollectionName(current => {
                        const preferred = selectedCollection || current
                        return items.includes(preferred) ? preferred : (items[0] || '')
                    })
                }
            } catch (err) {
                if (!cancelled) setError(err.message)
            }
        }

        loadCollections()
        return () => { cancelled = true }
    }, [selectedCollection])

    useEffect(() => {
        let cancelled = false

        setProjects([])
        setProjectName('')
        setSelectedProjects([])
        setAvailableWits([])
        setSelectedWit('')
        setResult(null)

        if (!collectionName) return

        async function loadProjects() {
            setOptionsLoading(true)
            try {
                const response = await fetch(
                    `/api/projects?collection_name=${encodeURIComponent(collectionName)}`
                )
                if (!response.ok) throw new Error('Projects could not be loaded.')

                const data = await response.json()
                if (!cancelled) setProjects(data.value || [])
            } catch (err) {
                if (!cancelled) setError(err.message)
            } finally {
                if (!cancelled) setOptionsLoading(false)
            }
        }

        loadProjects()
        return () => { cancelled = true }
    }, [collectionName])


    useEffect(() => {
        let cancelled = false

        setAvailableWits([])
        setSelectedWit('')
        setResult(null)

        const projectNames = multiProjectMode
            ? selectedProjects
            : (projectName ? [projectName] : [])

        if (!collectionName || projectNames.length === 0) return

        async function loadWits() {
            setOptionsLoading(true)
            setError('')

            try {
                const responses = await Promise.all(
                    projectNames.map(async name => {
                        const params = new URLSearchParams({
                            collection_name: collectionName,
                            project_name: name
                        })

                        const response = await fetch(`/api/work_item_type?${params}`)

                        if (!response.ok) {
                            throw new Error(`Work Item Types could not be loaded for ${name}.`)
                        }

                        const data = await response.json()
                        return (data.value || []).map(item => item.name)
                    })
                )

                const uniqueWits = [...new Set(responses.flat())].sort()

                if (!cancelled) {
                    setAvailableWits(uniqueWits)
                }
            } catch (err) {
                if (!cancelled) setError(err.message)
            } finally {
                if (!cancelled) setOptionsLoading(false)
            }
        }

        loadWits()

        return () => {
            cancelled = true
        }
    }, [collectionName, projectName, multiProjectMode, selectedProjects])

    const analyzeMultiProjects = async () => {
        if (!collectionName || selectedProjects.length === 0 || !selectedWit) {
            setError('Please select Collection, Projects and Work Item Type.')
            return
        }

        setLoading(true)
        setError('')
        setMultiAnalysisResult(null)
        setResult(null)
        setSelectedFields([])
        setBulkResult(null)
        setCheckResult(null)
        setApplyResult(null)

        try {
            const response = await fetch('/api/garbage/analyze-multi', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    collection_name: collectionName,
                    project_names: selectedProjects,
                    work_item_type: selectedWit,
                    start_date: startDate || null
                })
            })

            const data = await response.json()

            if (!response.ok) {
                throw new Error(
                    typeof data.detail === 'string'
                        ? data.detail
                        : 'Multi-Project analysis failed.'
                )
            }

            setMultiAnalysisResult(data)
        } catch (err) {
            setError(err.message)
        } finally {
            setLoading(false)
        }
    }
    const analyzeFields = async () => {
        if (!collectionName || !projectName || !selectedWit) {
            setError('Please select Collection, Project and Work Item Type.')
            return
        }
        setCheckResult(null)
        setCheckError('')
        setLoading(true)
        setError('')
        setResult(null)
        setSelectedFields([])
        setBulkResult(null)
        setBulkError('')
        try {
            const response = await fetch('/api/garbage/analyze', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    collection_name: collectionName,
                    project_name: projectName,
                    work_item_type: selectedWit,
                    start_date: startDate || null
                })
            })

            if (!response.ok) {
                const data = await response.json().catch(() => ({}))
                throw new Error(
                    typeof data.detail === 'string'
                        ? data.detail
                        : 'Garbage Cleanup analysis failed.'
                )
            }

            const data = await response.json()
            setResult(data)
        } catch (err) {
            setError(err.message)
        } finally {
            setLoading(false)
        }
    }
    const multiFields = (() => {
        if (!multiProjectMode || !multiAnalysisResult) return []

        const fieldMap = new Map()

        for (const project of multiAnalysisResult.results || []) {
            if (project.status !== 'analyzed') continue

            for (const field of project.data?.fields || []) {
                const existing = fieldMap.get(field.field_ref)

                if (existing) {
                    existing.projects.push(project.project_name)
                    existing.projectDetails.push({
                        project_name: project.project_name,
                        filled: field.filled,
                        total: field.total,
                        usage_rate: field.usage_rate,
                        candidate: field.candidate
                    })
                } else {
                    fieldMap.set(field.field_ref, {
                        ...field,
                        projects: [project.project_name],
                        projectDetails: [{
                            project_name: project.project_name,
                            filled: field.filled,
                            total: field.total,
                            usage_rate: field.usage_rate,
                            candidate: field.candidate
                        }]
                    })
                }
            }
        }

        return [...fieldMap.values()]
    })()
    const displayResult = multiProjectMode
        ? (multiAnalysisResult
            ? {
                start_date:
                    multiAnalysisResult.results.find(
                        item => item.status === 'analyzed'
                    )?.data?.start_date || 'N/A',

                total_work_items: multiAnalysisResult.results.reduce(
                    (sum, item) =>
                        sum + (item.status === 'analyzed'
                            ? (item.data?.total_work_items || 0)
                            : 0),
                    0
                ),

                total_fields: multiFields.length,

                cleanup_candidates: multiFields.filter(field =>
                    field.projectDetails.some(detail => detail.candidate)
                ).length,

                fields: multiFields
            }
            : null)
        : result
    const filteredFields = (
        multiProjectMode ? multiFields : (result?.fields || [])
    ).filter(field => {
        const matchesSearch =
            field.field_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
            field.field_ref.toLowerCase().includes(searchTerm.toLowerCase())

        const isCandidate = multiProjectMode
            ? field.projectDetails.some(detail => detail.candidate)
            : field.candidate

        return matchesSearch && (!candidateOnly || isCandidate)
    })
    const toggleField = (fieldRef) => {
        setBulkResult(null)
        setCheckResult(null)
        setCheckError('')
        setBulkError('')
        setSelectedFields(current =>
            current.includes(fieldRef)
                ? current.filter(ref => ref !== fieldRef)
                : [...current, fieldRef]
        )
    }

    const toggleAllFields = () => {
        setCheckResult(null)
        setCheckError('')
        setBulkResult(null)
        setBulkError('')
        const visibleRefs = filteredFields.map(field => field.field_ref)

        const allSelected = visibleRefs.every(ref =>
            selectedFields.includes(ref)
        )

        setSelectedFields(current =>
            allSelected
                ? current.filter(ref => !visibleRefs.includes(ref))
                : [...new Set([...current, ...visibleRefs])]
        )
    }
    const handleBulkPreviewClick = () => {
        const hasSystemField = selectedFields.some(ref =>
            ref.toLowerCase().startsWith('system.')
        )

        if (hasSystemField) {
            setShowSystemWarning(true)
            return
        }

        previewBulkCleanup()
    }
    const previewMultiCleanup = async () => {
        if (selectedFields.length === 0 || bulkLoading) return

        setBulkLoading(true)
        setBulkError('')
        setMultiPreviewResult(null)

        try {
            const results = []

            for (const projectName of selectedProjects) {
                const projectFields = multiFields
                    .filter(field =>
                        selectedFields.includes(field.field_ref) &&
                        field.projects.includes(projectName)
                    )
                    .map(field => field.field_ref)

                if (projectFields.length === 0) {
                    results.push({
                        project_name: projectName,
                        status: 'skipped',
                        message: 'No selected fields found in this project.'
                    })
                    continue
                }

                const response = await fetch('/api/garbage/preview-bulk', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        collection_name: collectionName,
                        project_name: projectName,
                        work_item_type: selectedWit,
                        field_refs: projectFields
                    })
                })

                const data = await response.json()

                results.push({
                    project_name: projectName,
                    status: response.ok && data.success ? 'ready' : 'error',
                    preview_id: data.preview_id || null,
                    field_refs: projectFields,
                    message: [
                        data.message,
                        data.details?.message,
                        typeof data.detail === 'string' ? data.detail : null,
                        ...(data.details?.dependencies || []).map(dep =>
                            `${dep.element} / ${dep.attribute || dep.location}: ${dep.value || ''}`
                        )
                    ].filter(Boolean).join(' — ')
                })
            }

            setMultiPreviewResult(results)
        } catch (err) {
            setBulkError(err.message)
        } finally {
            setBulkLoading(false)
        }
    }
    const previewBulkCleanup = async () => {
        if (selectedFields.length === 0 || bulkLoading) return
        setCheckResult(null)
        setCheckError('')
        setBulkLoading(true)
        setBulkError('')
        setBulkResult(null)

        try {
            const response = await fetch('/api/garbage/preview-bulk', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    collection_name: collectionName,
                    project_name: projectName,
                    work_item_type: selectedWit,
                    field_refs: selectedFields
                })
            })

            const data = await response.json()

            if (!response.ok || !data.success) {
                throw new Error(
                    data.details?.message ||
                    data.detail ||
                    data.message ||
                    'Bulk Cleanup preview failed.'
                )
            }

            setBulkResult(data)
        } catch (err) {
            setBulkError(err.message)
        } finally {
            setBulkLoading(false)
        }
    }
    const handleApplyClick = async () => {
        if (
            applyPreviewIds.length === 0 ||
            (multiProjectMode && multiPreviewHasErrors) ||
            checkLoading ||
            applyLoading ||
            applyResult ||
            applyError
        ) {
            return
        }

        setCheckLoading(true)
        setCheckError('')
        setCheckResult(null)

        try {
            const response = await fetch('/api/multi-projects/check-apply', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    preview_ids: applyPreviewIds,
                    confirm: true
                })
            })

            const data = await response.json()

            const results = data.results || []

            const allReady =
                results.length === applyPreviewIds.length &&
                results.every(item =>
                    item.ready === true &&
                    applyPreviewIds.includes(item.preview_id)
                )

            if (!response.ok || !data.success || !allReady) {
                const failedItems = results.filter(item => !item.ready)

                throw new Error(
                    failedItems.map(item =>
                        `${item.project_name}: ${item.message}`
                    ).join(' | ') ||
                    (typeof data.detail === 'string' ? data.detail : null) ||
                    data.message ||
                    'Preflight validation failed.'
                )
            }

            setCheckResult({
                ready: true,
                preview_ids: [...applyPreviewIds],
                results
            })

            setShowApplyConfirm(true)
        } catch (err) {
            setCheckError(err.message)
        } finally {
            setCheckLoading(false)
        }
    }
    const applyBulkCleanup = async () => {
        if (
            !checkResult?.ready ||
            !checkResult?.preview_ids?.length ||
            checkResult.preview_ids.length !== applyPreviewIds.length ||
            !checkResult.preview_ids.every(id => applyPreviewIds.includes(id)) ||
            (multiProjectMode && multiPreviewHasErrors) ||
            applyLoading
        ) {
            setShowApplyConfirm(false)
            setCheckError('Preview changed. Please run Check Apply again.')
            return
        }
        setShowApplyConfirm(false)
        setApplyLoading(true)
        setApplyError('')

        try {
            const response = await fetch('/api/multi-projects/apply', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    preview_ids: checkResult.preview_ids,
                    confirm: true
                })
            })

            const data = await response.json()

            const results = data.results || []

            const allSuccessful =
                results.length === checkResult.preview_ids.length &&
                results.every(item =>
                    item.success === true &&
                    checkResult.preview_ids.includes(item.preview_id)
                )

            if (!response.ok || !data.success || !allSuccessful || data.failed > 0) {
                const failedItems = results.filter(item => !item.success)

                throw new Error(
                    failedItems.map(item =>
                        `${item.project_name || item.preview_id}: ${item.message}`
                    ).join(' | ') ||
                    (typeof data.detail === 'string' ? data.detail : null) ||
                    data.detail?.message ||
                    data.message ||
                    'Apply failed. Check server and backup status.'
                )
            }

            setApplyResult(data)
            setCheckResult(null)
        } catch (err) {
            setApplyError(err.message)
            setCheckResult(null)
        } finally {
            setApplyLoading(false)
        }
    }
    const multiReadyPreviews = multiPreviewResult?.filter(
        item => item.status === 'ready' && item.preview_id
    ) || []
    const applyPreviewIds = multiProjectMode
        ? (multiPreviewResult || [])
            .filter(item => item.status === 'ready' && item.preview_id)
            .map(item => item.preview_id)
        : (bulkResult?.preview_id ? [bulkResult.preview_id] : [])
    const multiPreviewHasErrors = multiProjectMode && (
        !multiAnalysisResult ||
        (multiAnalysisResult.error_count || 0) > 0 ||
        (multiPreviewResult || []).some(item => item.status === 'error') ||
        (multiPreviewResult && multiPreviewResult.length !== selectedProjects.length)
    )

    const previewDisplay = multiProjectMode
        ? (multiPreviewResult
            ? {
                total_removed: multiReadyPreviews.reduce(
                    (sum, item) => sum + (item.field_refs?.length || 0), 0
                ),
                removed_fields: multiReadyPreviews.flatMap(item =>
                    (item.field_refs || []).map(field_ref => ({
                        field_ref,
                        project_name: item.project_name,
                        removed_controls: null
                    }))
                ),
                preview_ids: multiReadyPreviews.map(item => item.preview_id)
            }
            : null)
        : bulkResult
    return (
        <div className="garbage-cleanup">
            {applyResult?.success === true && (() => {
                const results = applyResult.results ?? []

                const committed = results.length > 0 &&
                    results.every(result =>
                        result.success === true &&
                        result.azure_backup?.success === true
                    )

                return (
                    <div className="gc-modal-overlay">
                        <div
                            className="gc-modal gc-apply-modal gc-success-modal"
                            role="alertdialog"
                            aria-modal="true"
                            aria-labelledby="gc-success-title"
                        >
                            <div className="gc-apply-modal-header">
                                <div className={`gc-apply-modal-icon ${committed ? 'gc-success-icon' : 'gc-warning-icon'}`}>
                                    {committed ? '✓' : '!'}
                                </div>
                                <div>
                                    <h3 id="gc-success-title">
                                        {committed
                                            ? 'Cleanup Applied Successfully'
                                            : 'Cleanup Applied — Repository Warning'}
                                    </h3>
                                </div>
                            </div>

                            <div className="gc-apply-modal-body">
                                <p>
                                    {committed
                                        ? 'XML changes were successfully applied, verified, and committed to Azure Repos.'
                                        : 'XML changes were applied and verified, but the Azure Repos commit could not be confirmed. Do not repeat Apply.'}
                                </p>
                            </div>

                            <div className="gc-apply-modal-footer">
                                <button
                                    type="button"
                                    className="gc-success-ok-btn"
                                    onClick={() => setApplyResult(null)}
                                >
                                    OK
                                </button>
                            </div>
                        </div>
                    </div>
                )
            })()}
            <h1>Garbage Cleanup</h1>
            <p>Analyze field usage and identify potential cleanup candidates.</p>

            <div className="workspace-panel">
                <div className="workspace-selectors">
                    <div className="collection-selector">
                        <label htmlFor="garbage-collection">Collection</label>
                        <select
                            id="garbage-collection"
                            value={collectionName}
                            onChange={e => {
                                setError('')
                                setCollectionName(e.target.value)
                            }}
                        >
                            <option value="">Select Collection</option>
                            {collections.map(name => (
                                <option key={name} value={name}>{name}</option>
                            ))}
                        </select>
                    </div>

                    <div className="collection-selector">
                        <label htmlFor="garbage-project-mode">Project Mode</label>

                        <select
                            id="garbage-project-mode"
                            value={multiProjectMode ? 'multi' : 'single'}
                            onChange={e => {
                                const isMulti = e.target.value === 'multi'

                                setMultiProjectMode(isMulti)
                                setSelectedProjects([])
                                setProjectName('')
                                setSelectedWit('')
                                setAvailableWits([])
                                setResult(null)
                                setSelectedFields([])
                                setBulkResult(null)
                                setCheckResult(null)
                                setApplyResult(null)
                                setError('')
                            }}
                        >
                            <option value="single">Single Project</option>
                            <option value="multi">Multi-Project</option>
                        </select>
                    </div>

                    <div className="collection-selector">
                        <label htmlFor="garbage-project">
                            {multiProjectMode ? 'Projects' : 'Project'}
                        </label>

                        {!multiProjectMode ? (
                            <select
                                id="garbage-project"
                                value={projectName}
                                disabled={!collectionName || optionsLoading}
                                onChange={e => {
                                    setError('')
                                    setProjectName(e.target.value)
                                }}
                            >
                                <option value="">Select Project</option>
                                {projects.map(project => (
                                    <option key={project.name} value={project.name}>
                                        {project.name}
                                    </option>
                                ))}
                            </select>
                        ) : (
                            <div className="gc-multi-project-list">
                                {projects.map(project => (
                                    <label key={project.name} className="gc-project-option">
                                        <input
                                            type="checkbox"
                                            checked={selectedProjects.includes(project.name)}
                                            disabled={optionsLoading}
                                            onChange={e => {
                                                setSelectedProjects(current =>
                                                    e.target.checked
                                                        ? [...current, project.name]
                                                        : current.filter(name => name !== project.name)
                                                )
                                            }}
                                        />
                                        <span>{project.name}</span>
                                    </label>
                                ))}

                                <small>{selectedProjects.length} projects selected</small>
                            </div>
                        )}
                    </div>

                    <div className="collection-selector">
                        <label htmlFor="garbage-wit">Work Item Type</label>
                        <select
                            id="garbage-wit"
                            value={selectedWit}
                            disabled={
                                optionsLoading ||
                                (multiProjectMode ? selectedProjects.length === 0 : !projectName)
                            } onChange={e => {
                                setSelectedWit(e.target.value)
                                setResult(null)
                            }}
                        >
                            <option value="">Select Work Item Type</option>
                            {availableWits.map(name => (
                                <option key={name} value={name}>{name}</option>
                            ))}
                        </select>
                    </div>

                    <div className="collection-selector">
                        <label htmlFor="garbage-date">Start Date (optional)</label>
                        <input
                            id="garbage-date"
                            type="date"
                            value={startDate}
                            max={new Date().toLocaleDateString('en-CA')}
                            onChange={e => {
                                setStartDate(e.target.value)
                                setResult(null)
                            }}
                        />
                        <small>
                            Leave empty to analyze the last 6 months.
                        </small>
                    </div>
                </div>

                <button
                    type="button"
                    onClick={multiProjectMode ? analyzeMultiProjects : analyzeFields}
                    disabled={
                        loading ||
                        optionsLoading ||
                        checkLoading ||
                        applyLoading ||
                        !!applyResult ||
                        !!applyError ||
                        !collectionName ||
                        !selectedWit ||
                        (multiProjectMode
                            ? selectedProjects.length === 0
                            : !projectName)
                    }
                >
                    {loading ? 'Analyzing...' : 'Analyze Fields'}
                </button>
            </div>

            {error && <p role="alert">{error}</p>}


            {loading && (
                <p role="status">
                    Analyzing Work Items and XML fields. This may take a while...
                </p>
            )}

            {displayResult && (
                <section className="garbage-results">
                    <h2>Analysis Results</h2>
                    <p>
                        Analysis start date: {displayResult.start_date}
                    </p>

                    <div className="garbage-stats">
                        <div>
                            <h3>{displayResult.total_work_items}</h3>
                            <p>Work Items</p>
                        </div>
                        <div>
                            <h3>{displayResult.total_fields}</h3>
                            <p>Fields Analyzed</p>
                        </div>
                        <div>
                            <h3>{displayResult.cleanup_candidates}</h3>
                            <p>Review Candidates</p>
                        </div>
                    </div>

                    <p>
                        Candidates indicate fields with no populated values in
                        the selected Work Items. They are not confirmed safe to delete.
                    </p>

                    <div className="garbage-filters">
                        <input
                            type="search"
                            placeholder="Search fields..."
                            value={searchTerm}
                            onChange={e => setSearchTerm(e.target.value)}
                            aria-label="Search fields"
                        />
                        <label>
                            <input
                                type="checkbox"
                                checked={candidateOnly}
                                onChange={e => setCandidateOnly(e.target.checked)}
                            />
                            Show review candidates only
                        </label>
                    </div>

                    <div style={{ overflowX: 'auto' }}>
                        <table className="garbage-table">
                            <thead>
                                <tr>
                                    <th>
                                        <input
                                            type="checkbox"
                                            aria-label="Select all visible fields"
                                            checked={
                                                filteredFields.length > 0 &&
                                                filteredFields.every(field =>
                                                    selectedFields.includes(field.field_ref)
                                                )
                                            }
                                            onChange={toggleAllFields}
                                        />
                                    </th>
                                    <th>Field Name</th>
                                    <th>Reference Name</th>
                                    {multiProjectMode && <th>Projects</th>}
                                    <th>Type</th>
                                    <th>Filled</th>
                                    <th>Usage</th>
                                    <th>Status</th>

                                </tr>
                            </thead>
                            <tbody>
                                {filteredFields.map(field => (
                                    <tr key={field.field_ref}>
                                        <td>
                                            <input
                                                type="checkbox"
                                                aria-label={`Select ${field.field_name}`}
                                                checked={selectedFields.includes(field.field_ref)}
                                                onChange={() => toggleField(field.field_ref)}
                                            />
                                        </td>
                                        <td>{field.field_name}</td>
                                        <td>{field.field_ref}</td>

                                        {multiProjectMode && (
                                            <td>
                                                {field.projects?.length === selectedProjects.length
                                                    ? `Common (${field.projects.length} projects)`
                                                    : field.projects?.join(', ')}
                                            </td>
                                        )}

                                        <td>{field.field_type}</td>
                                        <td>
                                            {multiProjectMode
                                                ? field.projectDetails?.map(detail => (
                                                    <div key={detail.project_name}>
                                                        <small>
                                                            {detail.project_name}: {detail.filled} / {detail.total}
                                                        </small>
                                                    </div>
                                                ))
                                                : `${field.filled} / ${field.total}`}
                                        </td>                                        <td>
                                            <div className="garbage-usage">
                                                <span className="garbage-usage-value">
                                                    {field.usage_rate}%
                                                </span>

                                                <div className="garbage-usage-track">
                                                    <div
                                                        className="garbage-usage-fill"
                                                        style={{
                                                            width: `${Math.min(100, Math.max(0, field.usage_rate))}%`
                                                        }}
                                                    />
                                                </div>
                                            </div>
                                        </td>
                                        <td>
                                            <span
                                                className={`garbage-status ${field.candidate
                                                    ? 'garbage-status-review'
                                                    : 'garbage-status-active'
                                                    }`}
                                            >
                                                <span className="garbage-status-dot" />
                                                {field.candidate ? 'Review Candidate' : 'In Use'}
                                            </span>
                                        </td>

                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                    <div className="garbage-selection-summary">
                        <span>
                            {selectedFields.length} field(s) selected
                        </span>

                        <button
                            type="button"
                            disabled={selectedFields.length === 0 || bulkLoading || loading}
                            onClick={multiProjectMode ? previewMultiCleanup : handleBulkPreviewClick}
                        >
                            {bulkLoading ? 'Preparing Preview...' : 'Preview Bulk Cleanup'}
                        </button>
                    </div>

                    {bulkError && (
                        <div className="garbage-bulk-error" role="alert">
                            <strong>Preview failed</strong>
                            <p>{bulkError}</p>
                        </div>
                    )}

                    {previewDisplay && (
                        <section className="gc-preview-panel">
                            <div className="gc-preview-header">
                                <div className="gc-preview-success-icon">✓</div>

                                <div className="gc-preview-heading">
                                    <h3>Bulk Cleanup Preview</h3>
                                    <p>Preview generated successfully</p>
                                </div>

                                <span className="gc-preview-status">
                                    Ready for review
                                </span>
                            </div>

                            <div className="gc-preview-stats">
                                <div className="gc-preview-stat">
                                    <span>Fields in preview</span>
                                    <strong>{previewDisplay.total_removed}</strong>
                                </div>

                                {!multiProjectMode && (
                                    <div className="gc-preview-stat">
                                        <span>Form controls removed</span>
                                        <strong>
                                            {previewDisplay.removed_fields.reduce(
                                                (total, field) =>
                                                    total + (field.removed_controls || 0),
                                                0
                                            )}
                                        </strong>
                                    </div>
                                )}

                                {multiProjectMode && (
                                    <div className="gc-preview-stat">
                                        <span>Projects ready</span>
                                        <strong>
                                            {multiReadyPreviews.length} / {selectedProjects.length}
                                        </strong>
                                    </div>
                                )}
                            </div>

                            <div className="gc-preview-changes">
                                <div className="gc-preview-section-heading">
                                    <h4>Proposed changes</h4>
                                    <span>
                                        {previewDisplay.removed_fields.length} field(s)                                    </span>
                                </div>

                                <div className="gc-preview-field-list">
                                    {previewDisplay.removed_fields.map(field => (<div
                                        className="gc-preview-field"
                                        key={`${field.project_name || 'single'}-${field.field_ref}`}                                        >
                                        <div className="gc-preview-field-info">
                                            <strong>{field.field_ref}</strong>
                                            <span>
                                                {multiProjectMode
                                                    ? field.project_name
                                                    : `${field.removed_controls} form control(s) removed`}
                                            </span>
                                        </div>

                                        {field.field_ref.toLowerCase().startsWith('system.') && (
                                            <span className="gc-preview-system-badge">
                                                System field
                                            </span>
                                        )}
                                    </div>
                                    ))}
                                </div>
                            </div>
                            {multiProjectMode && (
                                <div className="gc-preview-changes">
                                    <div className="gc-preview-section-heading">
                                        <h4>Project results</h4>
                                    </div>
                                    {(multiPreviewResult || []).map(item => (
                                        <div className="gc-preview-field" key={item.project_name}>
                                            <strong>{item.project_name}</strong>
                                            <span>
                                                {item.status === 'ready'
                                                    ? 'Ready'
                                                    : item.status === 'skipped'
                                                        ? 'Skipped'
                                                        : `Error: ${item.message || 'Preview failed'}`}
                                            </span>
                                        </div>
                                    ))}
                                    {multiPreviewHasErrors && (
                                        <p role="alert">
                                            Some project previews failed. Apply is unavailable.
                                        </p>
                                    )}
                                </div>
                            )}
                            <div className="gc-preview-notice">
                                <div className="gc-preview-notice-icon">
                                    <svg
                                        width="20"
                                        height="20"
                                        viewBox="0 0 24 24"
                                        fill="none"
                                        stroke="currentColor"
                                        strokeWidth="1.8"
                                        strokeLinecap="round"
                                        strokeLinejoin="round"
                                        aria-hidden="true"
                                    >
                                        <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z" />
                                        <path d="m9 12 2 2 4-4" />
                                    </svg>
                                </div>

                                <div className="gc-preview-notice-content">
                                    <strong>No changes applied to Azure DevOps</strong>
                                    <p>
                                        This is a preview-only operation. The proposed XML changes
                                        have been saved for review. No changes have been imported
                                        into the Azure DevOps Server.
                                    </p>
                                </div>

                                <span className="gc-preview-notice-label">
                                    PREVIEW ONLY
                                </span>
                            </div>
                            <div className="gc-apply-check">
                                <button
                                    type="button"
                                    className="gc-check-apply-btn"
                                    onClick={handleApplyClick}
                                    disabled={
                                        applyPreviewIds.length === 0 ||
                                        (multiProjectMode && multiPreviewHasErrors) ||
                                        checkLoading ||
                                        applyLoading ||
                                        !!applyResult ||
                                        !!applyError
                                    }
                                >
                                    {checkLoading
                                        ? 'Validating...'
                                        : applyLoading
                                            ? 'Applying...'
                                            : applyResult
                                                ? 'Applied'
                                                : 'Apply Changes'}
                                </button>

                                {checkError && (
                                    <p className="garbage-bulk-error" role="alert">
                                        {checkError}
                                    </p>
                                )}

                                {applyError && (
                                    <div className="garbage-bulk-error" role="alert">
                                        <strong>Apply requires investigation</strong>
                                        <p>{applyError}</p>
                                        <p>Check server and backup status before retrying.</p>
                                    </div>
                                )}
                            </div>
                            <div className="gc-preview-footer">
                                {multiProjectMode ? (
                                    <div className="gc-preview-id">
                                        <span>Preview IDs</span>
                                        {multiReadyPreviews.map(item => (
                                            <div key={item.preview_id}>
                                                <strong>{item.project_name}: </strong>
                                                <code>{item.preview_id}</code>
                                            </div>
                                        ))}
                                    </div>
                                ) : (
                                    <>
                                        <div className="gc-preview-id">
                                            <span>Preview ID</span>
                                            <code>{bulkResult.preview_id}</code>
                                        </div>
                                        <button
                                            type="button"
                                            className="gc-preview-copy"
                                            onClick={() =>
                                                navigator.clipboard.writeText(bulkResult.preview_id)
                                            }
                                        >
                                            Copy ID
                                        </button>
                                    </>
                                )}
                            </div>
                        </section>
                    )}
                    {showApplyConfirm && (
                        <div className="gc-modal-overlay">
                            <div
                                className="gc-modal gc-apply-modal"
                                role="alertdialog"
                                aria-modal="true"
                                aria-labelledby="gc-apply-title"
                                aria-describedby="gc-apply-description"
                            >
                                <div className="gc-apply-modal-header">
                                    <div className="gc-apply-modal-icon">!</div>

                                    <div>
                                        <h3 id="gc-apply-title">Confirm Bulk Remove</h3>
                                        <p id="gc-apply-description">
                                            Review the changes before applying them.
                                        </p>
                                    </div>
                                </div>

                                <div className="gc-apply-modal-body">
                                    <div className="gc-apply-target">
                                        <span>Target</span>
                                        <strong>
                                            {multiProjectMode
                                                ? `${(checkResult?.results || [])
                                                    .map(item => item.project_name)
                                                    .join(', ')} / ${selectedWit}`
                                                : `${projectName} / ${selectedWit}`
                                            }
                                        </strong>
                                    </div>

                                    <div className="gc-apply-fields-header">
                                        <strong>Fields to remove</strong>
                                        <span>
                                            {multiProjectMode
                                                ? `${(multiPreviewResult || [])
                                                    .filter(item => checkResult?.preview_ids?.includes(item.preview_id))
                                                    .reduce((total, item) => total + (item.field_refs?.length || 0), 0)} field removals`
                                                : `${bulkResult?.removed_fields?.length || 0} fields`}
                                        </span>
                                    </div>

                                    <div className="gc-apply-fields-list">
                                        {multiProjectMode
                                            ? (multiPreviewResult || [])
                                                .filter(item => checkResult?.preview_ids?.includes(item.preview_id))
                                                .flatMap(item =>
                                                    (item.field_refs || []).map(fieldRef => (
                                                        <div
                                                            className="gc-apply-field-item"
                                                            key={`${item.preview_id}-${fieldRef}`}
                                                        >
                                                            <span className="gc-apply-field-dot" />
                                                            <code>{item.project_name} / {fieldRef}</code>
                                                        </div>
                                                    ))
                                                )
                                            : bulkResult?.removed_fields?.map(field => (
                                                <div className="gc-apply-field-item" key={field.field_ref}>
                                                    <span className="gc-apply-field-dot" />
                                                    <code>{field.field_ref}</code>
                                                </div>
                                            ))}
                                    </div>

                                    <div className="gc-apply-backup-notice">
                                        <span className="gc-apply-backup-icon">✓</span>

                                        <div>
                                            <strong>Automatic backup enabled</strong>
                                            <p>
                                                A backup will be created before import.
                                                The updated XML will be verified afterward.
                                                Automatic rollback is not available.
                                            </p>
                                        </div>
                                    </div>
                                </div>

                                <div className="gc-modal-actions gc-apply-modal-actions">
                                    <button
                                        type="button"
                                        className="gc-apply-cancel-btn"
                                        onClick={() => setShowApplyConfirm(false)}
                                    >
                                        Cancel
                                    </button>

                                    <button
                                        type="button"
                                        className="gc-apply-confirm-btn"
                                        disabled={applyLoading}
                                        onClick={applyBulkCleanup}
                                    >
                                        {applyLoading ? 'Applying...' : 'Confirm & Apply'}
                                    </button>
                                </div>
                            </div>
                        </div>
                    )}
                    {showSystemWarning && (
                        <div className="gc-modal-overlay">
                            <div
                                className="gc-modal"
                                role="alertdialog"
                                aria-modal="true"
                                aria-labelledby="gc-modal-title"
                                aria-describedby="gc-modal-description"
                            >
                                <div className="gc-modal-header">
                                    <div className="gc-modal-icon">
                                        <svg
                                            width="24"
                                            height="24"
                                            viewBox="0 0 24 24"
                                            fill="none"
                                            stroke="currentColor"
                                            strokeWidth="1.8"
                                            strokeLinecap="round"
                                            strokeLinejoin="round"
                                            aria-hidden="true"
                                        >
                                            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z" />
                                            <path d="M12 8v5" />
                                            <path d="M12 17h.01" />
                                        </svg>
                                    </div>

                                    <div>
                                        <h3 id="gc-modal-title">
                                            System fields detected
                                        </h3>
                                        <span className="gc-modal-subtitle">
                                            Bulk Cleanup · Safety confirmation
                                        </span>
                                    </div>
                                </div>

                                <p
                                    id="gc-modal-description"
                                    className="gc-modal-description"
                                >
                                    Your selection contains Azure DevOps system fields.
                                    Changes to these fields may affect Work Item Type
                                    behavior and project functionality.
                                </p>

                                <div className="gc-modal-info">
                                    <strong>Preview only</strong>
                                    <p>
                                        Continuing will generate an XML preview.
                                        No changes will be applied to Azure DevOps.
                                    </p>
                                </div>

                                <div className="gc-modal-footer">
                                    <button
                                        type="button"
                                        className="gc-modal-cancel"
                                        onClick={() => setShowSystemWarning(false)}
                                    >
                                        Cancel
                                    </button>

                                    <button
                                        type="button"
                                        className="gc-modal-confirm"
                                        onClick={() => {
                                            setShowSystemWarning(false)
                                            previewBulkCleanup()
                                        }}
                                    >
                                        Continue to Preview
                                        <span aria-hidden="true">→</span>
                                    </button>
                                </div>
                            </div>
                        </div>
                    )}
                    {filteredFields.length === 0 && (
                        <p>No fields match the current filters.</p>
                    )}
                </section>
            )}

        </div>
    )
}

export default GarbageCleanup

