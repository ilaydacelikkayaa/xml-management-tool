import { useState, useEffect } from 'react'

function XmlFields({ selectedCollection }) {
    const [fields, setFields] = useState([])
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState('')
    const [searchTerm, setSearchTerm] = useState('')
    const [collections, setCollections] = useState([]);
    const [collectionsError, setCollectionsError] = useState('');
    const [projects, setProjects] = useState([]);
    const [selectedProjects, setSelectedProjects] = useState([]);
    const [selectedWit, setSelectedWit] = useState('')
    const [availableWits, setAvailableWits] = useState([])
    const [witsLoading, setWitsLoading] = useState(false)
    const [witError, setWitError] = useState('')
    const [projectsOpen, setProjectsOpen] = useState(false)
    const [operation, setOperation] = useState('add')
    const [fieldName, setFieldName] = useState('')
    const [fieldRef, setFieldRef] = useState('')
    const [fieldType, setFieldType] = useState('String')
    const [collectionName, setCollectionName] = useState(
        selectedCollection || ''
    )
    const [helpText, setHelpText] = useState('')
    const [isRequired, setIsRequired] = useState(false)
    const [showOnForm, setShowOnForm] = useState(true)
    const [isReadOnly, setIsReadOnly] = useState(false)
    const [updateRequired, setUpdateRequired] = useState('keep')
    const [updateReadOnly, setUpdateReadOnly] = useState('keep')
    const [updateVisibility, setUpdateVisibility] = useState('keep')
    const [updateHelpTextEnabled, setUpdateHelpTextEnabled] = useState(false)
    const [updateHelpText, setUpdateHelpText] = useState('')
    const [previewLoading, setPreviewLoading] = useState(false)
    const [previewResults, setPreviewResults] = useState([])
    const [fieldsLoaded, setFieldsLoaded] = useState(false)
    const [fieldsByProject, setFieldsByProject] = useState({})
    const [selectedDiff, setSelectedDiff] = useState(null)
    const [isEditingXml, setIsEditingXml] = useState(false)
    const [editedXml, setEditedXml] = useState('')
    const [savingXml, setSavingXml] = useState(false)
    const [xmlEditError, setXmlEditError] = useState('')
    const [xmlEditSuccess, setXmlEditSuccess] = useState('')
    const [diffLoading, setDiffLoading] = useState(false)
    const [diffError, setDiffError] = useState('')
    const [checkLoading, setCheckLoading] = useState(false)
    const [checkResults, setCheckResults] = useState([])
    const [checkError, setCheckError] = useState('')
    const [showApplyConfirm, setShowApplyConfirm] = useState(false)
    const [applySummary, setApplySummary] = useState(null)
    const [applySummaryLoading, setApplySummaryLoading] = useState(false)
    const [applySummaryError, setApplySummaryError] = useState('')
    const [loadedWit, setLoadedWit] = useState('')
    const [applyLoading, setApplyLoading] = useState(false)
    const [applyResult, setApplyResult] = useState(null)
    const [applyError, setApplyError] = useState('')
    useEffect(() => {
        let cancelled = false;

        async function loadCollections() {
            try {
                const response = await fetch('/api/collections');

                if (!response.ok) {
                    throw new Error('Collections could not be loaded.');
                }

                const data = await response.json();

                if (!cancelled) {
                    const items = Array.isArray(data) ? data : [];
                    setCollections(items);
                    setCollectionsError('');

                    setCollectionName(current => {
                        const preferred = selectedCollection || current;

                        if (preferred && items.includes(preferred)) {
                            return preferred;
                        }

                        return items[0] || '';
                    });
                }
            } catch (error) {
                if (!cancelled) {
                    setCollectionsError(error.message);
                }
            }
        }

        loadCollections();

        return () => {
            cancelled = true;
        };
    }, []);
    useEffect(() => {
        if (selectedCollection) {
            setCollectionName(selectedCollection)
        }
    }, [selectedCollection])
    useEffect(() => {
        let cancelled = false

        setSelectedWit('')
        setAvailableWits([])
        setPreviewResults([])
        setCheckResults([])
        setShowApplyConfirm(false)
        setFieldsLoaded(false)
        setFieldsByProject({})
        setWitError('')

        if (selectedProjects.length === 0) {
            setWitsLoading(false)
            return
        }

        async function loadWits() {
            setWitsLoading(true)

            try {
                const lists = await Promise.all(
                    selectedProjects.map(async (project) => {
                        const params = new URLSearchParams({
                            collection_name: collectionName,
                            project_name: project
                        })

                        const response = await fetch(`/api/work_item_type?${params}`)

                        if (!response.ok) {
                            throw new Error(`Could not load Work Item Types for ${project}`)
                        }

                        const data = await response.json()
                        return (data.value || []).map(item => item.name)
                    })
                )

                const commonWits = lists[0].filter(name =>
                    lists.every(list => list.includes(name))
                )

                if (!cancelled) {
                    setAvailableWits(commonWits)
                    if (commonWits.length === 0) {
                        setWitError('No common Work Item Types found.')
                    }
                }
            } catch (err) {
                if (!cancelled) setWitError(err.message)
            } finally {
                if (!cancelled) setWitsLoading(false)
            }
        }

        loadWits()

        return () => {
            cancelled = true
        }
    }, [collectionName, selectedProjects])
    const loadProjects = async () => {
        try {
            const response = await fetch(
                `/api/projects?collection_name=${encodeURIComponent(collectionName)}`
            );

            if (!response.ok) {
                throw new Error("Projeler alınamadı.");
            }

            const data = await response.json();
            console.log("React'e gelen projeler:", data.value);
            console.log("Projects API response:", data);
            setProjects(data.value || []);
            setSelectedProjects([]);
        } catch (error) {
            console.error("Project listesi hatası:", error);
            //setProjects([]);
        }
    };
    useEffect(() => {
        setProjects([]);
        setSelectedProjects([]);
        setSelectedWit('');
        setAvailableWits([]);
        setFieldsLoaded(false);
        setFieldsByProject({});
        setPreviewResults([]);
        setCheckResults([]);
        setShowApplyConfirm(false);
        setApplySummary(null);
        setApplySummaryError('');
        setApplyResult(null);
        setApplyError('');
        setSelectedDiff(null);
        setEditedXml('');
        setXmlEditError('');
        setXmlEditSuccess('');
        setLoadedWit('');

        loadProjects();
    }, [collectionName]);

    async function loadFields() {
        if (selectedProjects.length === 0) {
            setError('Please select at least one project.')
            return
        }
        if (!selectedWit) {
            setError('Please select a Work Item Type.')
            return
        }

        setFieldsLoaded(false)
        setLoading(true)
        setError('')
        setFieldsByProject({})
        setPreviewResults([])

        try {
            const results = {}

            for (const project of selectedProjects) {
                const params = new URLSearchParams({
                    collection_name: collectionName,
                    project_name: project,
                    work_item_type: selectedWit
                })

                const response = await fetch(`/api/xml-fields?${params}`)

                if (!response.ok) {
                    throw new Error(
                        `Failed to load fields for ${project}: HTTP ${response.status}`
                    )
                }

                const data = await response.json()

                if (!Array.isArray(data)) {
                    throw new Error(`Invalid fields response for ${project}`)
                }

                results[project] = data
            }

            setFieldsByProject(results)
            setLoadedWit(selectedWit)

            setFieldsLoaded(true)

        } catch (err) {
            setError(err.message)
        } finally {
            setLoading(false)
        }

    }
    async function handlePreview(event) {
        event.preventDefault()

        if (selectedProjects.length === 0) {
            setError('Please select at least one project.')
            return
        }

        if (!selectedWit) {
            setError('Please select a Work Item Type.')
            return
        }

        if (
            !fieldRef.trim() ||
            (operation === 'add' && !fieldName.trim())
        ) {
            setError('Please fill in the required fields.')
            return
        }

        setPreviewLoading(true)
        setPreviewResults([])
        setCheckResults([])
        setCheckError('')
        setSelectedDiff(null)
        setError('')
        setApplySummary(null)
        setApplySummaryError('')
        setShowApplyConfirm(false)

        try {
            const response = await fetch('/api/multi-projects/preview-field', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    collection_name: collectionName,
                    project_names: selectedProjects,
                    work_item_type: selectedWit,
                    operation: operation,
                    field_name: operation === 'remove' ? null : fieldName,
                    field_ref: fieldRef,
                    field_type: operation === 'add' ? fieldType : null,
                    help_text: operation === 'add'
                        ? helpText
                        : operation === 'update' && updateHelpTextEnabled
                            ? updateHelpText
                            : null,
                    is_required: operation === 'add'
                        ? isRequired
                        : operation === 'update' && updateRequired !== 'keep'
                            ? updateRequired === 'true'
                            : null,
                    is_read_only: operation === 'add'
                        ? isReadOnly
                        : operation === 'update' && updateReadOnly !== 'keep'
                            ? updateReadOnly === 'true'
                            : null,
                    show_on_form: operation === 'add'
                        ? showOnForm
                        : operation === 'update' && updateVisibility !== 'keep'
                            ? updateVisibility === 'true'
                            : null
                })
            })

            const data = await response.json()

            if (!response.ok) {
                throw new Error(
                    typeof data.detail === 'string'
                        ? data.detail
                        : `HTTP ${response.status}`
                )
            }

            const results = data.results || []

            setPreviewResults(results)
            console.log('PREVIEW DEBUG', {
                selectedProjects,
                results,
                selectedCount: selectedProjects.length,
                resultsCount: results.length
            })
            const allPreviewsSuccessful =
                results.length === selectedProjects.length &&
                results.every(
                    result => result.success === true && result.preview_id
                )
            console.log('REMOVE PREVIEW DEBUG:', {
                selectedProjects,
                results,
                expectedCount: selectedProjects.length,
                actualCount: results.length,
                failedResults: results.filter(
                    result => result.success !== true || !result.preview_id
                )
            })
            if (allPreviewsSuccessful) {
                await handleCheckApply(results)
            } else {
                setCheckError(
                    'Preview validation incomplete. Review the affected projects before continuing.'
                )
            }

        } catch (err) {
            setError(err.message)
        } finally {
            setPreviewLoading(false)
        }
    }
    async function handleViewChanges(previewId) {
        setDiffLoading(true)
        setDiffError('')
        setSelectedDiff(null)

        try {
            const response = await fetch(
                `/api/previews/${encodeURIComponent(previewId)}/diff`
            )

            if (!response.ok) {
                throw new Error(`Failed to load XML changes: HTTP ${response.status}`)
            }

            const data = await response.json()
            setSelectedDiff(data)

            setEditedXml(data.modified_xml ?? '')
            setIsEditingXml(false)
        } catch (err) {
            setDiffError(err.message)
        } finally {
            setDiffLoading(false)
        }
    }

    async function handleSaveXmlEdit() {
        if (!selectedDiff?.preview_id || savingXml) return

        const sourcePreviewId = selectedDiff.preview_id

        setSavingXml(true)
        setXmlEditError('')
        setXmlEditSuccess('')

        try {
            const response = await fetch(
                `/api/previews/${encodeURIComponent(sourcePreviewId)}/manual-edit`,
                {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        modified_xml: editedXml,
                    }),
                }
            )

            const data = await response.json()

            if (!response.ok || data.success !== true) {
                throw new Error(
                    typeof data.detail === 'string'
                        ? data.detail
                        : 'XML kaydedilemedi.'
                )
            }

            setCheckResults([])
            setCheckError('')

            setShowApplyConfirm(false)
            setApplySummary(null)
            setApplySummaryError('')

            setApplyResult(null)
            setApplyError('')
            // Manuel düzenleme yalnızca tek proje için destekleniyor.
            if (selectedProjects.length !== 1 || previewResults.length !== 1) {
                throw new Error(
                    'Manual XML editing currently supports one project only.'
                )
            }

            const previousPreview = previewResults[0]

            if (
                previousPreview.success !== true ||
                previousPreview.preview_id !== sourcePreviewId ||
                previousPreview.project_name !== selectedProjects[0]
            ) {
                throw new Error(
                    'The edited XML does not match the selected project preview.'
                )
            }

            // Yeni Preview ID'sini aktif hale getir.
            setPreviewResults([
                {
                    ...previousPreview,
                    preview_id: data.preview_id,
                    operation: 'manual_edit',
                    success: true,
                    ready: false,
                    message: 'Manual XML preview saved. Apply validation is pending.',
                },
            ])
            setSelectedDiff(null)
            setIsEditingXml(false)

            setXmlEditSuccess(
                `XML doğrulandı. Yeni Preview ID: ${data.preview_id}`
            )

            await handleViewChanges(data.preview_id)
            await handleCheckApply([
                {
                    ...previousPreview,
                    preview_id: data.preview_id,
                    operation: 'manual_edit',
                    success: true,
                    ready: false,
                    project_name: selectedProjects[0],
                },
            ])
        } catch (error) {
            setXmlEditError(error.message || 'XML kaydedilemedi.')
        } finally {
            setSavingXml(false)
        }
    }
    async function handleCheckApply(results = previewResults) {

        const previewIds = results
            .filter(result => result.success && result.preview_id)
            .map(result => result.preview_id)

        if (previewIds.length === 0) {
            setCheckError('No successful previews to check.')
            return
        }

        setCheckLoading(true)
        setCheckError('')
        setCheckResults([])

        try {
            const response = await fetch('/api/multi-projects/check-apply', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    preview_ids: previewIds,
                    confirm: true
                })
            })

            const data = await response.json()

            if (!response.ok) {
                throw new Error(
                    typeof data.detail === 'string'
                        ? data.detail
                        : 'Preflight check failed.'
                )
            }

            if (!Array.isArray(data.results) || data.results.length === 0) {
                throw new Error('Backend did not return check results.')
            }

            setCheckResults(data.results)

        } catch (error) {
            setCheckError(error.message)
        } finally {
            setCheckLoading(false)
        }
    }
    async function handleOpenApplyConfirm() {
        if (
            !['add', 'update', 'remove', 'manual_edit'].includes(operation) ||
            selectedProjects.length === 0 ||
            previewResults.length !== selectedProjects.length ||
            checkResults.length !== selectedProjects.length
        ) {
            setApplySummaryError('All projects must pass validation.')
            return
        }

        const validProjects = selectedProjects.every(projectName => {
            const preview = previewResults.find(
                item => item.project_name === projectName
            )
            const check = checkResults.find(
                item => item.project_name === projectName
            )

            return (
                preview?.success === true &&
                check?.ready === true &&
                Boolean(preview?.preview_id) &&
                check?.preview_id === preview.preview_id
            )
        })

        if (!validProjects) {
            setApplySummaryError('Some projects failed validation.')
            return
        }

        setApplySummaryLoading(true)
        setApplySummaryError('')
        setApplySummary(null)
        setShowApplyConfirm(false)

        try {
            const summaries = await Promise.all(
                selectedProjects.map(async projectName => {
                    const preview = previewResults.find(
                        item => item.project_name === projectName
                    )

                    const response = await fetch(
                        `/api/work-item-types/previews/${encodeURIComponent(preview.preview_id)}/summary`
                    )

                    const data = await response.json()

                    if (!response.ok) {
                        throw new Error(`Summary failed for ${projectName}`)
                    }

                    if (
                        data.success !== true ||
                        data.preview_id !== preview.preview_id ||
                        data.project_name !== projectName ||
                        data.collection_name !== collectionName ||
                        data.work_item_type !== selectedWit ||
                        (
                            preview.operation === 'manual_edit'
                                ? (
                                    data.operation !== 'manual_edit' ||
                                    selectedProjects.length !== 1
                                )
                                : (
                                    data.operation !== operation ||
                                    data.field_ref !== fieldRef
                                )
                        )
                    ) {
                        throw new Error(`Preview mismatch for ${projectName}`)
                    }

                    return data
                })
            )

            setApplySummary(summaries)
            setShowApplyConfirm(true)

        } catch (error) {
            setApplySummaryError(error.message)
        } finally {
            setApplySummaryLoading(false)
        }
    }
    async function handleApply() {
        if (applyLoading) return

        const valid =
            showApplyConfirm &&
            Array.isArray(applySummary) &&
            applySummary.length === selectedProjects.length &&
            selectedProjects.length > 0 &&
            previewResults.length === selectedProjects.length &&
            checkResults.length === selectedProjects.length &&
            selectedProjects.every(projectName => {
                const preview = previewResults.find(
                    item => item.project_name === projectName
                )

                const check = checkResults.find(
                    item => item.project_name === projectName
                )

                const summary = applySummary.find(
                    item => item.project_name === projectName
                )

                const isManualEdit = preview?.operation === 'manual_edit'

                const operationValid = isManualEdit
                    ? (
                        selectedProjects.length === 1 &&
                        summary?.operation === 'manual_edit'
                    )
                    : (
                        ['add', 'update', 'remove'].includes(operation) &&
                        summary?.operation === operation &&
                        summary?.field_ref === fieldRef
                    )

                return (
                    preview?.success === true &&
                    check?.ready === true &&
                    Boolean(preview?.preview_id) &&
                    check?.preview_id === preview.preview_id &&
                    summary?.preview_id === preview.preview_id &&
                    summary?.project_name === projectName &&
                    summary?.collection_name === collectionName &&
                    summary?.work_item_type === selectedWit &&
                    operationValid
                )
            })

        if (!valid) {
            setApplyError('Import security validation failed.')
            return
        }

        const previewIds = selectedProjects.map(
            projectName =>
                previewResults.find(
                    item => item.project_name === projectName
                ).preview_id
        )

        setApplyLoading(true)
        setApplyError('')
        setApplyResult(null)

        try {
            const response = await fetch('/api/multi-projects/apply', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    preview_ids: previewIds,
                    confirm: true
                })
            })

            const data = await response.json()

            if (response.ok && data.success === true) {
                await loadFields()
            } setApplyResult(data)
            setShowApplyConfirm(false)
            setCheckResults([])
            setPreviewResults([])

            if (!response.ok || data.success !== true) {
                const projectErrors = (data.results ?? [])
                    .filter(result => result.success !== true)
                    .map(result => {
                        const message = result.message
                        return `${result.project_name ?? 'Project'}: ${typeof message === 'string'
                            ? message
                            : JSON.stringify(message)
                            }`
                    })

                const errorMessage =
                    projectErrors.join('\n') ||
                    (typeof data.detail === 'string'
                        ? data.detail
                        : data.detail
                            ? JSON.stringify(data.detail)
                            : data.message || 'Unknown import error.')

                setApplyError(errorMessage)
            }
        } catch (error) {
            setApplyError(
                'Import response could not be confirmed. ' +
                'Check server state before retrying. ' + error.message
            )
        } finally {
            setApplyLoading(false)
        }
    }

    function resetApplyState() {
        setPreviewResults([])
        setCheckResults([])
        setCheckError('')
        setSelectedDiff(null)
        setApplySummary(null)
        setApplySummaryError('')
        setShowApplyConfirm(false)
    }
    const canApply =
        selectedProjects.length > 0 &&
        ['add', 'update', 'remove'].includes(operation) &&
        !applySummaryLoading &&
        !applyLoading &&
        !previewLoading &&
        !checkLoading &&
        previewResults.length === selectedProjects.length &&
        checkResults.length === selectedProjects.length &&
        selectedProjects.every(projectName => {
            const preview = previewResults.find(
                result => result.project_name === projectName
            )

            const check = checkResults.find(
                result => result.project_name === projectName
            )

            return (
                preview?.success === true &&
                check?.ready === true &&
                Boolean(preview?.preview_id) &&
                check?.preview_id === preview.preview_id
            )
        })


    return (
        <section>
            {applyResult?.success === true && (() => {
                const results = applyResult.results ?? []
                const allCommitted =
                    results.length === applyResult.total_projects &&
                    results.every(result =>
                        result.success === true &&
                        result.azure_backup?.success === true
                    )

                return (
                    <div className="warning-overlay">
                        <div
                            className="warning-modal"
                            role="alertdialog"
                            aria-modal="true"
                            aria-labelledby="import-success-title"
                        >
                            <div className="warning-header">
                                <span aria-hidden="true">
                                    {allCommitted ? '✓' : '!'}
                                </span>
                                <h2 id="import-success-title">
                                    {allCommitted
                                        ? 'Changes Applied Successfully'
                                        : 'XML Applied — Repository Sync Warning'}
                                </h2>
                            </div>

                            <div className="warning-body">
                                {allCommitted ? (
                                    <p>
                                        All {applyResult.total_projects} project(s)
                                        were imported, verified, and committed
                                        to Azure Repos successfully.
                                    </p>
                                ) : (
                                    <p>
                                        XML changes were imported and verified,
                                        but Azure Repos commit could not be confirmed
                                        for every project. Check repository status
                                        before making further changes.
                                        Do not repeat Apply.
                                    </p>
                                )}
                            </div>

                            <div className="warning-footer">
                                <button
                                    type="button"
                                    onClick={() => setApplyResult(null)}
                                >
                                    OK
                                </button>
                            </div>
                        </div>
                    </div>
                )
            })()}
            {applyError && (
                <div className="warning-overlay">
                    <div
                        className="warning-modal"
                        role="alertdialog"
                        aria-modal="true"
                        aria-labelledby="warning-title"
                        aria-describedby="warning-description"
                    >
                        <div className="warning-header">
                            <span className="warning-symbol" aria-hidden="true">
                                !
                            </span>
                            <h2 id="warning-title">Import verification warning</h2>
                        </div>

                        <div className="warning-body">
                            <p id="warning-description" style={{ whiteSpace: 'pre-wrap' }}>
                                {applyError}
                            </p>
                        </div>

                        <div className="warning-footer">
                            <button
                                type="button"
                                onClick={() => setApplyError('')}
                            >
                                OK
                            </button>
                        </div>
                    </div>
                </div>
            )}
            <h1>XML Fields</h1>

            <p>Manage Work Item Type fields.</p>

            <div className="workspace-panel">
                <div className="workspace-selectors">

                    <div className="collection-selector">
                        <label htmlFor="collection">Collection</label>
                        <select
                            id="collection"
                            value={collectionName}
                            onChange={(event) => setCollectionName(event.target.value)}
                        >
                            {collections.map(collection => (
                                <option key={collection} value={collection}>
                                    {collection}
                                </option>
                            ))}
                        </select>

                        {collectionsError && (
                            <p role="alert">{collectionsError}</p>
                        )}

                    </div>

                    <div className="collection-selector">
                        <label>Projects (Teams)</label>

                        <div className="project-dropdown">
                            <button
                                type="button"
                                className="project-dropdown-trigger"
                                onClick={() => setProjectsOpen(!projectsOpen)}
                            >
                                <span>
                                    {selectedProjects.length > 0
                                        ? `${selectedProjects.length} projects selected`
                                        : 'Select projects...'}
                                </span>
                                <span>{projectsOpen ? '⌃' : '⌄'}</span>
                            </button>
                            {projectsOpen && (
                                <div className="project-dropdown-menu">
                                    {projects.map((project) => (
                                        <label
                                            key={project.name}
                                            className="project-dropdown-option"
                                        >
                                            <input
                                                type="checkbox"
                                                checked={selectedProjects.includes(project.name)}
                                                onChange={(event) => {
                                                    setPreviewResults([])
                                                    setCheckResults([])
                                                    setCheckError('')
                                                    setApplySummary(null)
                                                    setApplySummaryError('')
                                                    setShowApplyConfirm(false)
                                                    if (event.target.checked) {
                                                        setSelectedProjects((previous) => [
                                                            ...previous,
                                                            project.name
                                                        ])
                                                    } else {
                                                        setSelectedProjects((previous) =>
                                                            previous.filter(
                                                                (name) => name !== project.name
                                                            )
                                                        )
                                                    }
                                                }}
                                            />
                                            <span>{project.name}</span>
                                        </label>
                                    ))}
                                </div>
                            )}
                        </div>
                    </div>

                </div>
                <div className="collection-selector">
                    <label htmlFor="work-item-type">Work Item Type</label>

                    <select
                        id="work-item-type"
                        value={selectedWit}
                        disabled={selectedProjects.length === 0 || witsLoading}
                        onChange={(event) => {
                            setSelectedWit(event.target.value)
                            setPreviewResults([])
                            setCheckResults([])
                            setShowApplyConfirm(false)
                            setFieldsLoaded(false)
                            setFieldsByProject({})
                        }}
                    >
                        <option value="">
                            {witsLoading
                                ? 'Loading Work Item Types...'
                                : 'Select Work Item Type'}
                        </option>

                        {availableWits.map(wit => (
                            <option key={wit} value={wit}>
                                {wit}
                            </option>
                        ))}
                    </select>

                    {witError && <p className="error-message">{witError}</p>}
                </div>

                <div className="workspace-actions">
                    <button
                        type="button"
                        className="xml-action-btn"
                        onClick={loadFields}
                        disabled={loading}
                    >
                        {loading ? 'Loading...' : 'Load Fields'}
                    </button>
                </div>
            </div>
            {fieldsLoaded && (
                <div className="field-operations">
                    <div className="operations-header">
                        <h2>Field Operations</h2>
                        <p>Add or remove fields from selected projects.</p>
                    </div>

                    <div className="operation-tabs">
                        <button
                            type="button"
                            className={operation === 'add' ? 'active' : ''}
                            onClick={() => {
                                setOperation('add')
                                setPreviewResults([])
                                setCheckResults([])
                                setCheckError('')
                                setApplySummary(null)
                                setApplySummaryError('')
                                setShowApplyConfirm(false)
                            }}
                        >
                            + Add Field
                        </button>
                        <button
                            type="button"
                            className={operation === 'update' ? 'active' : ''}
                            onClick={() => {
                                setOperation('update')
                                setPreviewResults([])
                                setSelectedDiff(null)
                                setCheckResults([])
                                setCheckError('')
                                setApplySummary(null)
                                setApplySummaryError('')
                                setShowApplyConfirm(false)
                            }}
                        >
                            Update Field
                        </button>
                        <button
                            type="button"
                            className={operation === 'remove' ? 'active' : ''}
                            onClick={() => {
                                setOperation('remove')
                                setPreviewResults([])
                                setCheckResults([])
                                setCheckError('')
                                setApplySummary(null)
                                setApplySummaryError('')
                                setShowApplyConfirm(false)
                            }}
                        >
                            − Remove Field
                        </button>
                    </div>

                    <form
                        className="field-operation-form"
                        onSubmit={handlePreview}
                    >{(operation === 'add' || operation === 'update') && (
                        <div className="form-group">
                            <label htmlFor="field-name">
                                {operation === 'update' ? 'New Field Name (Optional)' : 'Field Name'}
                            </label>
                            <input
                                id="field-name"
                                value={fieldName}
                                onChange={(event) => {
                                    setFieldName(event.target.value)
                                    resetApplyState()
                                }}
                                placeholder={
                                    operation === 'update'
                                        ? 'e.g. Updated System Code'
                                        : 'e.g. Flag'
                                }
                                required={operation === 'add'} />
                        </div>
                    )}

                        <div className="form-group">
                            <label htmlFor="field-ref">Reference Name</label>
                            <input
                                id="field-ref"
                                value={fieldRef}
                                onChange={(event) => {
                                    setFieldRef(event.target.value)
                                    resetApplyState()
                                }}
                                placeholder="e.g. Lab.Flag"
                                required
                            />
                        </div>

                        {operation === 'add' && (
                            <div className="form-group">
                                <label htmlFor="field-type">Field Type</label>
                                <select
                                    id="field-type"
                                    value={fieldType}
                                    onChange={(event) => {
                                        setFieldType(event.target.value)
                                        resetApplyState()
                                    }}
                                >
                                    <option value="String">String</option>
                                    <option value="Integer">Integer</option>
                                    <option value="DateTime">DateTime</option>
                                    <option value="Boolean">Boolean</option>
                                </select>
                            </div>
                        )}

                        {operation === 'update' && (
                            <div className="field-update-settings">
                                <p>Choose only the settings you want to change. Keep existing leaves a setting unchanged.</p>
                                <div className="form-group">
                                    <label htmlFor="update-required">Required</label>
                                    <select id="update-required" value={updateRequired} onChange={e => { setUpdateRequired(e.target.value); resetApplyState() }}>
                                        <option value="keep">Keep existing</option>
                                        <option value="true" disabled={updateReadOnly === 'true'}>
                                            Enable
                                        </option>
                                        <option value="false">Disable</option>
                                    </select>
                                </div>
                                <div className="form-group">
                                    <label htmlFor="update-readonly">Read Only</label>
                                    <select id="update-readonly" value={updateReadOnly} onChange={e => { setUpdateReadOnly(e.target.value); resetApplyState() }}>
                                        <option value="keep">Keep existing</option>
                                        <option value="true" disabled={updateRequired === 'true'}>
                                            Enable
                                        </option>
                                        <option value="false">Disable</option>
                                    </select>
                                </div>
                                <div className="form-group">
                                    <label htmlFor="update-visibility">Show on Form</label>
                                    <select id="update-visibility" value={updateVisibility} onChange={e => { setUpdateVisibility(e.target.value); resetApplyState() }}>
                                        <option value="keep">Keep existing</option>
                                        <option value="true">Show</option>
                                        <option value="false">Hide</option>
                                    </select>
                                </div>
                                <div className="form-group">
                                    <label>
                                        <input type="checkbox" checked={updateHelpTextEnabled} onChange={e => { setUpdateHelpTextEnabled(e.target.checked); resetApplyState() }} />
                                        Change Help Text
                                    </label>
                                    {updateHelpTextEnabled && (
                                        <input value={updateHelpText} onChange={e => { setUpdateHelpText(e.target.value); resetApplyState() }} placeholder="New help text (empty to clear)" />
                                    )}
                                </div>
                            </div>
                        )}

                        {operation === 'add' && (
                            <>
                                <div className="form-group">
                                    <label htmlFor="help-text">Help Text</label>
                                    <input
                                        id="help-text"
                                        value={helpText}
                                        onChange={(event) => setHelpText(event.target.value)}
                                        placeholder="e.g. Indicates whether this item is flagged"
                                    />
                                </div>

                                <div className="field-options">
                                    <label>
                                        <input
                                            type="checkbox"
                                            checked={isRequired}
                                            onChange={(event) => setIsRequired(event.target.checked)}
                                        />
                                        Required
                                    </label>

                                    <label>
                                        <input
                                            type="checkbox"
                                            checked={isReadOnly}
                                            onChange={(event) => setIsReadOnly(event.target.checked)}
                                        />
                                        Read Only
                                    </label>

                                    <label>
                                        <input
                                            type="checkbox"
                                            checked={showOnForm}
                                            onChange={(event) => setShowOnForm(event.target.checked)}
                                        />
                                        Show on Form
                                    </label>
                                </div>
                            </>
                        )}


                        <button
                            type="submit"
                            className="xml-action-btn"
                            disabled={
                                selectedProjects.length === 0 ||
                                previewLoading ||
                                checkLoading
                            }
                        >
                            {previewLoading || checkLoading
                                ? 'Validating Changes...'
                                : 'Preview & Validate'}
                        </button>
                    </form>


                    {previewResults.length > 0 && (
                        <div className="preview-results">
                            <div className="preview-results-header">
                                <div>
                                    <h3>Project Validation Results</h3>
                                    <p>Preview and preflight validation for {previewResults.length} projects</p>
                                </div>
                                <span className="preview-count">
                                    {previewResults.filter(result => {
                                        const check = checkResults.find(
                                            item => item.preview_id === result.preview_id
                                        )

                                        return result.success && check?.ready === true
                                    }).length}/{previewResults.length} Ready
                                </span>
                            </div>

                            <div className="preview-results-list">
                                {previewResults.map((result) => (
                                    <div className="preview-result-card" key={result.project_name}>
                                        <div className="preview-result-top">
                                            <strong>{result.project_name}</strong>
                                            <span className={result.success ? 'preview-success' : 'preview-failed'}>
                                                {result.success ? '✓ Success' : '✕ Failed'}
                                            </span>
                                        </div>

                                        <p>
                                            {result.success
                                                ? 'Preview created successfully'
                                                : result.message}
                                        </p>
                                        <div className="project-validation-steps">
                                            <div className="validation-step">
                                                <span className="validation-step-label">Preview</span>
                                                <span className={result.success ? 'preview-success' : 'preview-failed'}>
                                                    {result.success ? '✓ Generated' : '✕ Failed'}
                                                </span>
                                            </div>

                                            <div className="validation-step">
                                                <span className="validation-step-label">Preflight</span>

                                                {(() => {
                                                    const check = checkResults.find(
                                                        item => item.preview_id === result.preview_id
                                                    )

                                                    if (!check) {
                                                        return <span className="validation-pending">Not checked</span>
                                                    }

                                                    return (
                                                        <span className={check.ready ? 'preflight-ready' : 'preflight-not-ready'}>
                                                            {check.ready ? '✓ Ready' : '✕ Not Ready'}
                                                        </span>
                                                    )
                                                })()}
                                            </div>
                                        </div>

                                        {result.preview_id && (
                                            <div className="preview-id-row">
                                                <code>{result.preview_id}</code>
                                                <button
                                                    type="button"
                                                    onClick={() => navigator.clipboard.writeText(result.preview_id)}
                                                >
                                                    Copy
                                                </button>
                                                <button
                                                    type="button"
                                                    onClick={() => handleViewChanges(result.preview_id)}
                                                    disabled={diffLoading}
                                                >
                                                    View Changes
                                                </button>
                                            </div>
                                        )}
                                    </div>
                                ))}
                            </div>

                            <div className="preview-info">
                                ✓ Preview only — No changes have been imported to the server.
                            </div>


                            {showApplyConfirm && Array.isArray(applySummary) && (
                                <div className="apply-confirm-overlay">
                                    <div
                                        className="apply-confirm-modal"
                                        role="alertdialog"
                                        aria-modal="true"
                                        aria-labelledby="apply-confirm-title"
                                        aria-describedby="apply-confirm-description"
                                    >
                                        <div className="apply-confirm-header">
                                            <div className="apply-confirm-icon">!</div>
                                            <div>
                                                <h2 id="apply-confirm-title">Confirm Changes</h2>
                                                <p id="apply-confirm-description">
                                                    Review the changes before applying them to Azure DevOps Server.
                                                </p>
                                            </div>
                                        </div>

                                        <div className="apply-confirm-details">
                                            <div className="apply-confirm-detail-row">
                                                <span>Collection</span>
                                                <strong>{collectionName}</strong>
                                            </div>

                                            <div className="apply-confirm-detail-row">
                                                <span>Work Item Type</span>
                                                <strong>{selectedWit}</strong>
                                            </div>

                                            <div className="apply-confirm-detail-row">
                                                <span>Projects</span>
                                                <strong>{applySummary.length}</strong>
                                            </div>
                                        </div>

                                        <div className="apply-confirm-projects">
                                            {applySummary.map(summary => (
                                                <div
                                                    key={summary.preview_id}
                                                    className="apply-confirm-project"
                                                >
                                                    <div className="apply-confirm-project-heading">
                                                        <h3>{summary.project_name}</h3>
                                                        <span className="apply-confirm-operation">
                                                            {summary.operation}
                                                        </span>
                                                    </div>

                                                    <div className="apply-confirm-field">
                                                        <span>Field Name</span>
                                                        <strong>{summary.field_name}</strong>
                                                    </div>

                                                    <div className="apply-confirm-field">
                                                        <span>Reference Name</span>
                                                        <code>{summary.field_ref}</code>
                                                    </div>
                                                </div>
                                            ))}
                                        </div>

                                        <div className="apply-confirm-warning">
                                            <span className="apply-confirm-warning-icon">!</span>
                                            <p>
                                                A backup will be created before each import.
                                                If a project fails, changes to earlier projects
                                                may already have been applied.
                                            </p>
                                        </div>

                                        <div className="apply-confirm-actions">
                                            <button
                                                type="button"
                                                className="apply-confirm-cancel"
                                                onClick={() => setShowApplyConfirm(false)}
                                                disabled={applyLoading}
                                            >
                                                Cancel
                                            </button>

                                            <button
                                                type="button"
                                                className="apply-confirm-submit"
                                                onClick={handleApply}
                                                disabled={applyLoading}
                                            >
                                                {applyLoading ? 'Importing...' : 'Apply Changes'}
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            )}

                            {applyResult && (
                                <div className="import-result">
                                    <div className="import-result-header">
                                        <h3>
                                            {applyResult.success
                                                ? 'Import Completed Successfully'
                                                : applyResult.successful > 0
                                                    ? 'Import Partially Completed'
                                                    : 'Import Could Not Be Verified'}
                                        </h3>

                                        <p>
                                            {applyResult.successful ?? 0} of{' '}
                                            {applyResult.total_projects ?? 0} projects
                                            successfully verified.
                                        </p>
                                    </div>

                                    <div className="import-result-stats">
                                        <span>Total: {applyResult.total_projects ?? 0}</span>
                                        <span>Verified: {applyResult.successful ?? 0}</span>
                                        <span>Needs review: {applyResult.failed ?? 0}</span>
                                    </div>

                                    <div className="import-result-projects">
                                        {(applyResult.results ?? []).map((result) => (
                                            <div
                                                key={result.preview_id}
                                                className="import-result-project"
                                            >
                                                <div>
                                                    <strong>{result.project_name}</strong>
                                                    <p>
                                                        {result.success
                                                            ? 'Import completed and verified.'
                                                            : 'Import or verification requires review.'}
                                                    </p>
                                                </div>

                                                <span>
                                                    {result.success ? '✓ Verified' : '⚠ Review required'}
                                                </span>
                                            </div>
                                        ))}
                                    </div>

                                    {!applyResult.success && (
                                        <p className="import-result-warning">
                                            One or more projects could not be verified.
                                            Review the existing server state before retrying.
                                        </p>
                                    )}
                                </div>
                            )}

                            <div className="check-apply-actions">

                                <button
                                    type="button"
                                    className="xml-action-btn"
                                    disabled={!canApply}
                                    onClick={handleOpenApplyConfirm}
                                >
                                    {applySummaryLoading ? 'Loading Preview...' : 'Apply Changes'}
                                </button>
                            </div>

                            {applySummaryError && (
                                <p style={{ color: 'red' }}>{applySummaryError}</p>
                            )}

                            {checkError && (
                                <div className="apply-confirm-overlay">
                                    <div
                                        className="apply-confirm-modal"
                                        role="alertdialog"
                                        aria-modal="true"
                                        aria-labelledby="preview-warning-title"
                                        aria-describedby="preview-warning-description"
                                    >
                                        <h3 id="preview-warning-title">
                                            Preview Validation Incomplete
                                        </h3>

                                        <p id="preview-warning-description">
                                            {checkError}
                                        </p>

                                        <div className="preview-warning-actions">
                                            <button
                                                type="button"
                                                onClick={() => setCheckError('')}
                                            >
                                                OK
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            )}

                            {diffLoading && <p>Loading XML comparison...</p>}

                            {diffError && <p style={{ color: 'red' }}>{diffError}</p>}

                            {selectedDiff && (
                                <div className="xml-diff-viewer">
                                    <div className="xml-diff-header">
                                        <h4>XML Comparison</h4>
                                        <div className="xml-edit-actions">
                                            {isEditingXml && (
                                                <button
                                                    type="button"
                                                    onClick={handleSaveXmlEdit}
                                                    disabled={savingXml || !editedXml.trim()}
                                                >
                                                    {savingXml ? 'Validating...' : 'Save & Validate'}
                                                </button>
                                            )}

                                            <button
                                                type="button"
                                                disabled={savingXml}
                                                onClick={() => {
                                                    if (isEditingXml) {
                                                        setEditedXml(selectedDiff.modified_xml ?? '')
                                                    }

                                                    setIsEditingXml(!isEditingXml)
                                                    setXmlEditError('')
                                                }}
                                            >
                                                {isEditingXml ? 'Cancel Editing' : 'Edit XML'}
                                            </button>
                                        </div>
                                    </div>
                                    {xmlEditError && (
                                        <p className="preview-error" role="alert">
                                            {xmlEditError}
                                        </p>
                                    )}

                                    <div className="xml-diff-columns">
                                        <div className="xml-diff-panel">
                                            <h4>Original XML</h4>

                                            {selectedDiff.changes.map((change, index) =>
                                                change.original_lines.map((line, lineIndex) => (
                                                    <pre
                                                        key={`${index}-${lineIndex}`}
                                                        className={
                                                            change.type === 'delete' || change.type === 'replace'
                                                                ? 'xml-line-removed'
                                                                : 'xml-line'
                                                        }
                                                    >
                                                        {line || ' '}
                                                    </pre>
                                                ))
                                            )}
                                        </div>

                                        <div className="xml-diff-panel">
                                            <h4>Modified XML</h4>


                                            {xmlEditSuccess && (
                                                <p className="preview-success">{xmlEditSuccess}</p>
                                            )}
                                            {isEditingXml ? (
                                                <textarea
                                                    className="xml-edit-textarea"
                                                    value={editedXml}
                                                    onChange={(event) => setEditedXml(event.target.value)}
                                                    spellCheck={false}
                                                />
                                            ) : (
                                                selectedDiff.changes.map((change, index) =>
                                                    change.modified_lines.map((line, lineIndex) => (
                                                        <pre
                                                            key={`${index}-${lineIndex}`}
                                                            className={
                                                                change.type === 'insert' || change.type === 'replace'
                                                                    ? 'xml-line-added'
                                                                    : 'xml-line'
                                                            }
                                                        >
                                                            {line || ' '}
                                                        </pre>
                                                    ))
                                                )
                                            )}
                                        </div>
                                    </div>

                                    <div className="xml-diff-legend">
                                        <span>🔴 Red — Removed lines</span>
                                        <span>🔵 Blue — Added lines</span>
                                    </div>
                                </div>
                            )}


                        </div>
                    )}

                    {error && <p style={{ color: 'red' }}>{error}</p>}

                    <div className="fields-toolbar">
                        <h2>Work Item Fields</h2>

                        <input
                            className="field-search"
                            type="text"
                            placeholder="Search fields..."
                            value={searchTerm}
                            onChange={(event) => setSearchTerm(event.target.value)}
                        />
                    </div>

                    {
                        fieldsLoaded && Object.entries(fieldsByProject).map(([project, projectFields]) => {
                            const filtered = projectFields.filter((field) => {
                                const search = searchTerm.toLowerCase()

                                return (
                                    field.name.toLowerCase().includes(search) ||
                                    field.refname.toLowerCase().includes(search) ||
                                    field.field_type.toLowerCase().includes(search)
                                )
                            })

                            return (
                                <div className="fields-table-container" key={project}>
                                    <div className="fields-table-heading">
                                        <div>
                                            <h3>{project}</h3>
                                            <p>
                                                Work Item Type: <strong>{loadedWit}</strong>
                                                {' · '}
                                                {projectFields.length} fields
                                            </p>
                                        </div>
                                    </div>

                                    <table className="fields-table">
                                        <thead>
                                            <tr>
                                                <th>Field Name</th>
                                                <th>Reference Name</th>
                                                <th>Type</th>
                                            </tr>
                                        </thead>

                                        <tbody>
                                            {filtered.map((field) => (
                                                <tr key={field.refname}>
                                                    <td>{field.name}</td>
                                                    <td>{field.refname}</td>
                                                    <td>{field.field_type}</td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            )
                        })
                    }

                </div>
            )}
        </section>
    )
}

export default XmlFields