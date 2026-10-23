
import { useState, useEffect } from 'react'
import { createPortal } from "react-dom";

function GlobalLists({ selectedCollection }) {
    const [collectionName, setCollectionName] = useState(
        selectedCollection || 'XMLLabCollection'
    )
    const [globalLists, setGlobalLists] = useState([])
    const [listName, setListName] = useState('')
    const [configOpen, setConfigOpen] = useState(true)

    const [operation, setOperation] = useState('add')
    const [itemValue, setItemValue] = useState('')
    const [oldValue, setOldValue] = useState('')
    const [newValue, setNewValue] = useState('')
    const [showSuccessModal, setShowSuccessModal] = useState(false);
    const [loading, setLoading] = useState(false)
    const [loaded, setLoaded] = useState(false)
    const [previewLoading, setPreviewLoading] = useState(false)
    const [error, setError] = useState('')
    const [previewResult, setPreviewResult] = useState(null)
    const [applyLoading, setApplyLoading] = useState(false)
    const [applyError, setApplyError] = useState('')
    const [applyResult, setApplyResult] = useState(null)
    const [confirmApply, setConfirmApply] = useState(false)
    const [selectedDiff, setSelectedDiff] = useState(null)
    const [diffLoading, setDiffLoading] = useState(false)
    const [diffError, setDiffError] = useState('')

    function getGlobalListValues(xmlText, listName) {
        if (!xmlText) return []

        const parser = new DOMParser()
        const xmlDocument = parser.parseFromString(xmlText, 'application/xml')

        if (xmlDocument.querySelector('parsererror')) {
            throw new Error('Preview XML could not be parsed.')
        }

        const lists = Array.from(
            xmlDocument.getElementsByTagName('GLOBALLIST')
        )

        const selectedList = lists.find(
            (list) => list.getAttribute('name') === listName
        )

        if (!selectedList) {
            throw new Error('Selected GlobalList was not found in preview XML.')
        }

        return Array.from(
            selectedList.getElementsByTagName('LISTITEM')
        ).map((item) => item.getAttribute('value'))
    }

    async function loadGlobalLists() {
        setLoading(true)
        setLoaded(false)
        setError('')
        setGlobalLists([])
        setListName('')
        setPreviewResult(null)
        setApplyResult(null)
        setApplyError('')

        try {
            const response = await fetch(
                `/global-lists?collection_name=${encodeURIComponent(collectionName)}`
            )

            const data = await response.json()

            if (!response.ok || !data.success) {
                throw new Error(
                    typeof data.detail === 'string'
                        ? data.detail
                        : 'GlobalList verileri alınamadı.'
                )
            }

            const lists = data.global_lists ?? []

            setGlobalLists(lists)
            setListName(lists[0]?.name ?? '')
            setLoaded(true)
        } catch (err) {
            setError(err.message)
        } finally {
            setLoading(false)
        }
    }
    useEffect(() => {
        if (selectedCollection) {
            setCollectionName(selectedCollection)
        }
    }, [selectedCollection])
    useEffect(() => {
        if (!collectionName) return;

        loadGlobalLists();
    }, [collectionName]);

    const selectedList = globalLists.find(
        (list) => list.name === listName
    );

    const currentValues = selectedList?.values ?? [];

    let previewValues = [];
    let previewParseError = "";

    if (previewResult?.preview_xml) {
        try {
            previewValues = getGlobalListValues(
                previewResult.preview_xml,
                previewResult.list_name || listName
            );
        } catch (err) {
            previewParseError = err.message;
        }
    }

    const beforeValues = currentValues
    const afterValues = previewValues

    function changeCollection(value) {
        setCollectionName(value)
        setGlobalLists([])
        setListName('')
        setLoaded(false)
        setPreviewResult(null)
        setApplyResult(null)
        setApplyError('')
        setConfirmApply(false)
        setSelectedDiff(null)
        setDiffError('')
        setError('')
    }

    function changeOperation(nextOperation) {
        setOperation(nextOperation)
        setItemValue('')
        setOldValue('')
        setNewValue('')
        setPreviewResult(null)
        setApplyResult(null)
        setApplyError('')
        setConfirmApply(false)
        setSelectedDiff(null)
        setDiffError('')
        setError('')
    }

    async function handlePreview(event) {
        event.preventDefault()

        if (!listName || !loaded || loading) return

        setPreviewLoading(true)
        setError('')
        setPreviewResult(null)
        setApplyResult(null)
        setApplyError('')
        setConfirmApply(false)
        setSelectedDiff(null)
        setDiffError('')

        const endpoints = {
            add: '/global-lists/preview-add',
            update: '/global-lists/preview-update',
            remove: '/global-lists/preview-remove'
        }

        const body = {
            collection_name: collectionName,
            list_name: listName
        }

        if (operation === 'update') {
            body.old_value = oldValue
            body.new_value = newValue
        } else {
            body.item_value = itemValue
        }

        try {
            const response = await fetch(endpoints[operation], {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(body)
            })

            const data = await response.json()

            if (!response.ok || !data.success) {
                const message = typeof data.detail === 'string'
                    ? data.detail
                    : data.message || 'Preview oluşturulamadı.'

                throw new Error(message)
            }

            setPreviewResult(data)
        } catch (err) {
            setError(err.message)
        } finally {
            setPreviewLoading(false)
        }
    }
    async function handleApply() {
        if (!previewResult?.success || !previewResult?.preview_id) return
        if (previewResult.collection_name && previewResult.collection_name !== collectionName) {
            setApplyError('Preview belongs to another collection. Generate a new preview.')
            setConfirmApply(false)
            return
        }

        setApplyLoading(true)
        setApplyError('')
        setApplyResult(null)

        try {
            const response = await fetch('/global-lists/apply', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    preview_id: previewResult.preview_id,
                    confirm: true
                })
            })

            const data = await response.json()

            if (!response.ok || !data.success) {
                throw new Error(
                    typeof data.detail === 'string'
                        ? data.detail
                        : data.message || 'GlobalList import failed.'
                )
            }

            setApplyResult(data);
            setConfirmApply(false);
            setPreviewResult(null);

            await loadGlobalLists();

            setShowSuccessModal(true);

        } catch (err) {
            setApplyError(err.message)
            setConfirmApply(false)
        } finally {
            setApplyLoading(false)
        }
    }

    async function handleViewChanges(previewId) {
        setDiffLoading(true)
        setDiffError('')
        setSelectedDiff(null)

        try {
            const response = await fetch(
                `/global-lists/previews/${encodeURIComponent(previewId)}/diff`
            )

            if (!response.ok) {
                throw new Error(`Failed to load XML changes: HTTP ${response.status}`)
            }

            const data = await response.json()
            setSelectedDiff(data)

        } catch (err) {
            setDiffError(err.message)
        } finally {
            setDiffLoading(false)
        }
    }

    return (
        <section>
            <p className="breadcrumb">MANAGEMENT / GLOBAL LISTS</p>
            <h1>GlobalLists</h1>
            <p>Manage Azure DevOps GlobalList values.</p>

            <div className="workspace-panel global-config-panel">
                <button
                    type="button"
                    className="section-toggle"
                    aria-expanded={configOpen}
                    onClick={() => setConfigOpen(!configOpen)}
                >
                    <span>Collection Configuration</span>
                    <span>{configOpen ? '⌃' : '⌄'}</span>
                </button>

                {configOpen && (
                    <>
                        <div className="workspace-selectors">
                            <div className="collection-selector">
                                <label htmlFor="global-collection">Collection</label>
                                <select
                                    id="global-collection"
                                    value={collectionName}
                                    disabled={loading || previewLoading}
                                    onChange={(e) => changeCollection(e.target.value)}
                                >
                                    <option value="XMLLabCollection">
                                        XMLLabCollection
                                    </option>
                                    <option value="XMLTestCollection">
                                        XMLTestCollection
                                    </option>
                                </select>
                            </div>

                            <div className="collection-selector">
                                <label htmlFor="global-list-name">GlobalList</label>
                                <select
                                    id="global-list-name"
                                    value={listName}
                                    disabled={!loaded || loading || previewLoading || globalLists.length === 0}
                                    onChange={(e) => {
                                        setListName(e.target.value)
                                        setItemValue('')
                                        setOldValue('')
                                        setNewValue('')
                                        setPreviewResult(null)
                                    }}
                                >
                                    {!loaded && (
                                        <option value="">Load GlobalLists first</option>
                                    )}

                                    {loaded && globalLists.length === 0 && (
                                        <option value="">No GlobalLists found</option>
                                    )}

                                    {globalLists.map((list) => (
                                        <option key={list.name} value={list.name}>
                                            {list.name}
                                        </option>
                                    ))}
                                </select>
                            </div>
                        </div>

                        <div className="global-load-actions">
                            {loading && (
                                <span className="global-loaded-status">
                                    Loading GlobalLists...
                                </span>
                            )}

                            {loaded && (
                                <span className="global-loaded-status">
                                    ✓ {globalLists.length} GlobalList loaded
                                </span>
                            )}
                        </div>
                    </>
                )}
            </div>
            {error && (
                <p className="global-error" role="alert">
                    {error}
                </p>
            )}

            {selectedList && (
                <div className="global-values-panel">
                    <h2>Existing List Items — {listName}</h2>

                    {currentValues.length === 0 ? (
                        <p>No values found in this GlobalList.</p>
                    ) : (
                        <div className="global-values">
                            {currentValues.map((value, index) => (
                                <span className="global-value-chip" key={`${value}-${index}`}>
                                    {value}
                                </span>
                            ))}
                        </div>
                    )}
                </div>
            )}

            <div className="field-operations">
                <div className="operations-header">
                    <h2>GlobalList Operations</h2>
                    <p>Add, update or remove values from a GlobalList.</p>
                </div>

                <div className="operation-tabs">
                    <button
                        type="button"
                        className={operation === 'add' ? 'active' : ''}
                        onClick={() => changeOperation('add')}
                        disabled={previewLoading}
                    >
                        + Add Item
                    </button>

                    <button
                        type="button"
                        className={operation === 'update' ? 'active' : ''}
                        onClick={() => changeOperation('update')}
                        disabled={previewLoading}
                    >
                        Update Item
                    </button>

                    <button
                        type="button"
                        className={operation === 'remove' ? 'active' : ''}
                        onClick={() => changeOperation('remove')}
                        disabled={previewLoading}
                    >
                        − Remove Item
                    </button>
                </div>

                <form className="field-operation-form" onSubmit={handlePreview}>
                    {operation === 'update' ? (
                        <>
                            <div className="form-group">
                                <label htmlFor="old-value">Current Value</label>
                                <select
                                    id="old-value"
                                    value={oldValue}
                                    onChange={(e) => { setOldValue(e.target.value); setPreviewResult(null) }}
                                    disabled={!loaded || previewLoading}
                                    required
                                >
                                    <option value="">Select a value</option>
                                    {currentValues.map((value, index) => (
                                        <option key={`${value}-${index}`} value={value}>
                                            {value}
                                        </option>
                                    ))}
                                </select>
                            </div>

                            <div className="form-group">
                                <label htmlFor="new-value">New Value</label>
                                <input
                                    id="new-value"
                                    value={newValue}
                                    onChange={(e) => { setNewValue(e.target.value); setPreviewResult(null) }}
                                    placeholder="e.g. Staging"
                                    disabled={!loaded || previewLoading}
                                    required
                                />
                            </div>
                        </>
                    ) : operation === 'remove' ? (
                        <div className="form-group">
                            <label htmlFor="item-value">Item to Remove</label>
                            <select
                                id="item-value"
                                value={itemValue}
                                onChange={(e) => { setItemValue(e.target.value); setPreviewResult(null) }}
                                disabled={!loaded || previewLoading}
                                required
                            >
                                <option value="">Select a value</option>
                                {currentValues.map((value, index) => (
                                    <option key={`${value}-${index}`} value={value}>
                                        {value}
                                    </option>
                                ))}
                            </select>
                        </div>
                    ) : (
                        <div className="form-group">
                            <label htmlFor="item-value">New Item Value</label>
                            <input
                                id="item-value"
                                value={itemValue}
                                onChange={(e) => { setItemValue(e.target.value); setPreviewResult(null) }}
                                placeholder="e.g. Staging"
                                disabled={!loaded || previewLoading}
                                required
                            />
                        </div>
                    )}

                    <button
                        type="submit"
                        className="xml-action-btn"
                        disabled={!loaded || loading || previewLoading || !listName}
                    >
                        {previewLoading ? 'Generating Preview...' : 'Preview Changes'}
                    </button>
                </form>

                <div className="preview-info">
                    ✓ Preview only — No changes have been imported to the server.
                </div>


                {previewResult && (
                    <div className="preview-results">
                        <div className="preview-results-header">
                            <h2>Preview Result</h2>
                        </div>

                        <p className="preview-success">
                            ✓ {previewResult.message || 'Preview created successfully.'}
                        </p>

                        {previewResult.preview_id && (
                            <div className="preview-id-row">
                                <code>{previewResult.preview_id}</code>

                                <button
                                    type="button"
                                    onClick={() => handleViewChanges(previewResult.preview_id)}
                                    disabled={diffLoading}
                                >
                                    View Changes
                                </button>
                            </div>
                        )}


                        {previewResult.preview_xml && (
                            <div className="global-comparison">
                                <h3>Changes Preview — {previewResult.list_name || listName}</h3>

                                {previewParseError ? (
                                    <p className="global-error">{previewParseError}</p>
                                ) : (
                                    <div className="global-comparison-grid">

                                        <div className="global-comparison-column">
                                            <h4>Before</h4>
                                            <p>Currently loaded values</p>

                                            {beforeValues.length === 0 && (
                                                <p className="global-no-values">No values</p>
                                            )}

                                            {beforeValues.map((value, index) => {
                                                const isRemoved = !afterValues.includes(value)

                                                return (
                                                    <div
                                                        key={`${value}-${index}`}
                                                        className={
                                                            isRemoved
                                                                ? 'global-compare-item removed'
                                                                : 'global-compare-item'
                                                        }
                                                    >
                                                        <span>{isRemoved ? '−' : '•'}</span>
                                                        {value}
                                                    </div>
                                                )
                                            })}
                                        </div>

                                        <div className="global-comparison-column">
                                            <h4>After</h4>
                                            <p>Values in the preview XML</p>

                                            {afterValues.length === 0 && (
                                                <p className="global-no-values">No values</p>
                                            )}

                                            {afterValues.map((value, index) => {
                                                const isAdded = !beforeValues.includes(value)

                                                return (
                                                    <div
                                                        key={`${value}-${index}`}
                                                        className={
                                                            isAdded
                                                                ? 'global-compare-item added'
                                                                : 'global-compare-item'
                                                        }
                                                    >
                                                        <span>{isAdded ? '+' : '•'}</span>
                                                        {value}
                                                    </div>
                                                )
                                            })}
                                        </div>

                                    </div>
                                )}

                                <details className="global-xml-details">
                                    <summary>View Preview XML</summary>
                                    <pre>{previewResult.preview_xml}</pre>
                                </details>
                            </div>
                        )}

                        {previewResult?.success && previewResult?.preview_id && !applyResult?.success && (
                            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 24, paddingTop: 20, borderTop: '1px solid #e5e7eb' }}>
                                <button
                                    type="button"
                                    className="xml-action-btn"
                                    disabled={applyLoading || previewLoading || loading}
                                    onClick={() => { setApplyError(''); setConfirmApply(true) }}
                                >
                                    {applyLoading ? 'Importing...' : 'Apply Changes'}
                                </button>
                            </div>
                        )}
                    </div>
                )}
            </div>

            {diffLoading && (
                <p>Loading XML comparison...</p>
            )}

            {diffError && (
                <p className="global-error" role="alert">
                    {diffError}
                </p>
            )}

            {selectedDiff && (
                <div className="xml-diff-viewer">
                    <div className="xml-diff-header">
                        <h3>XML Changes — {listName}</h3>

                        <button
                            type="button"
                            onClick={() => setSelectedDiff(null)}
                        >
                            Close
                        </button>
                    </div>

                    <div className="xml-diff-columns">
                        <div className="xml-diff-panel">
                            <h4>Original XML</h4>

                            {selectedDiff.changes.map((change, index) =>
                                change.original_lines.map((line, lineIndex) => (
                                    <pre
                                        key={`${index}-${lineIndex}`}
                                        className={
                                            change.type === 'delete' ||
                                                change.type === 'replace'
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

                            {selectedDiff.changes.map((change, index) =>
                                change.modified_lines.map((line, lineIndex) => (
                                    <pre
                                        key={`${index}-${lineIndex}`}
                                        className={
                                            change.type === 'insert' ||
                                                change.type === 'replace'
                                                ? 'xml-line-added'
                                                : 'xml-line'
                                        }
                                    >
                                        {line || ' '}
                                    </pre>
                                ))
                            )}
                        </div>
                    </div>

                    <div className="xml-diff-legend">
                        <span>🔴 Red — Removed lines</span>
                        <span>🔵 Blue — Added lines</span>
                    </div>
                </div>
            )}
            {confirmApply && (
                <div
                    className="global-confirm-overlay"
                    style={{ position: 'fixed', inset: 0, zIndex: 9999, background: 'rgba(15, 23, 42, 0.68)', backdropFilter: 'blur(3px)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 20 }}
                >
                    <div
                        className="global-confirm-modal"
                        role="alertdialog"
                        aria-modal="true"
                        aria-labelledby="global-apply-title"
                        aria-describedby="global-apply-description"
                        style={{ width: 'min(520px, 100%)', maxHeight: '90vh', overflowY: 'auto', borderRadius: 18, background: '#fff', color: '#172033', boxShadow: '0 25px 80px rgba(0,0,0,0.3)', padding: 30 }}
                    >
                        <div style={{ display: 'flex', gap: 14, alignItems: 'flex-start', marginBottom: 22 }}>
                            <div aria-hidden="true" style={{ width: 44, height: 44, flexShrink: 0, display: 'grid', placeItems: 'center', borderRadius: 12, background: '#fff4e5', color: '#b45309', fontSize: 24 }}>!</div>
                            <div>
                                <h2 id="global-apply-title" style={{ margin: '0 0 6px', fontSize: 21, fontWeight: 700 }}>Confirm Apply Changes</h2>
                                <p id="global-apply-description" style={{ margin: 0, color: '#64748b', lineHeight: 1.5 }}>Review the changes before importing them into Azure DevOps Server.</p>
                            </div>
                        </div>

                        <div style={{ border: '1px solid #e2e8f0', borderRadius: 12, overflow: 'hidden', marginBottom: 18 }}>
                            <div style={{ padding: '12px 16px', display: 'flex', justifyContent: 'space-between', gap: 12, background: '#f8fafc', borderBottom: '1px solid #e2e8f0' }}>
                                <span style={{ color: '#64748b' }}>Collection</span><strong>{collectionName}</strong>
                            </div>
                            <div style={{ padding: '12px 16px', display: 'flex', justifyContent: 'space-between', gap: 12, borderBottom: '1px solid #e2e8f0' }}>
                                <span style={{ color: '#64748b' }}>GlobalList</span><strong>{previewResult?.list_name || listName}</strong>
                            </div>
                            <div style={{ padding: '12px 16px', display: 'flex', justifyContent: 'space-between', gap: 12, borderBottom: '1px solid #e2e8f0' }}>
                                <span style={{ color: '#64748b' }}>Operation</span><strong style={{ textTransform: 'capitalize' }}>{operation}</strong>
                            </div>
                            <div style={{ padding: '12px 16px', display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'center' }}>
                                <span style={{ color: '#64748b' }}>Change</span>
                                <strong style={{ textAlign: 'right', overflowWrap: 'anywhere' }}>
                                    {operation === 'update' ? `${oldValue} → ${newValue}` : operation === 'add' ? `+ ${itemValue}` : `− ${itemValue}`}
                                </strong>
                            </div>
                        </div>

                        <div style={{ background: '#eff6ff', border: '1px solid #bfdbfe', borderRadius: 12, padding: '13px 15px', color: '#1e40af', lineHeight: 1.55, fontSize: 14 }}>
                            A backup will be created before import. This change affects the collection-level GlobalList and may impact projects that use it.
                        </div>

                        {applyError && <p role="alert" style={{ color: '#b91c1c' }}>{applyError}</p>}

                        <div style={{ display: 'flex', justifyContent: 'flex-end', flexWrap: 'wrap', gap: 12, marginTop: 26 }}>
                            <button type="button" disabled={applyLoading} onClick={() => setConfirmApply(false)} style={{ border: '1px solid #cbd5e1', borderRadius: 9, background: '#fff', color: '#334155', padding: '11px 18px', fontWeight: 600, cursor: 'pointer' }}>Cancel</button>
                            <button type="button" disabled={applyLoading} onClick={handleApply} style={{ border: 0, borderRadius: 9, background: '#2563eb', color: '#fff', padding: '11px 18px', fontWeight: 600, cursor: applyLoading ? 'wait' : 'pointer', opacity: applyLoading ? 0.7 : 1 }}>
                                {applyLoading ? 'Importing...' : 'Confirm Apply'}
                            </button>
                        </div>
                    </div>
                </div>
            )}
            {applyError && (
                <p className="global-error" role="alert">
                    {applyError}
                </p>
            )}


            {showSuccessModal &&
                createPortal(
                    <div
                        role="presentation"
                        style={{
                            position: "fixed",
                            inset: 0,
                            zIndex: 9999,
                            background: "rgba(15, 23, 42, 0.48)",
                            backdropFilter: "blur(3px)",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            padding: "20px",
                        }}
                    >
                        <div
                            role="alertdialog"
                            aria-modal="true"
                            aria-labelledby="global-list-success-title"
                            aria-describedby="global-list-success-description"
                            style={{
                                width: "100%",
                                maxWidth: "420px",
                                background: "#ffffff",
                                borderRadius: "16px",
                                padding: "32px",
                                textAlign: "center",
                                boxShadow: "0 24px 70px rgba(0, 0, 0, 0.22)",
                                boxSizing: "border-box",
                            }}
                        >
                            <div
                                style={{
                                    width: "64px",
                                    height: "64px",
                                    borderRadius: "50%",
                                    background: "#ECFDF5",
                                    color: "#059669",
                                    display: "flex",
                                    alignItems: "center",
                                    justifyContent: "center",
                                    margin: "0 auto 20px",
                                    fontSize: "30px",
                                    fontWeight: "bold",
                                }}
                            >
                                ✓
                            </div>

                            <h2
                                id="global-list-success-title"
                                style={{
                                    fontSize: "22px",
                                    fontWeight: 650,
                                    color: "#0F172A",
                                    margin: "0 0 12px",
                                }}
                            >
                                Changes Applied Successfully
                            </h2>

                            <p
                                id="global-list-success-description"
                                style={{
                                    fontSize: "14px",
                                    lineHeight: 1.7,
                                    color: "#64748B",
                                    margin: "0 0 26px",
                                }}
                            >
                                Your GlobalList changes have been successfully
                                applied and verified on Azure DevOps Server.
                            </p>

                            <button
                                type="button"
                                onClick={() => setShowSuccessModal(false)}
                                style={{
                                    width: "100%",
                                    padding: "12px 20px",
                                    background: "#2563EB",
                                    color: "#FFFFFF",
                                    border: "none",
                                    borderRadius: "9px",
                                    fontSize: "14px",
                                    fontWeight: 600,
                                    cursor: "pointer",
                                }}
                            >
                                Done
                            </button>
                        </div>
                    </div>,
                    document.body
                )}
        </section >
    )
}


export default GlobalLists
