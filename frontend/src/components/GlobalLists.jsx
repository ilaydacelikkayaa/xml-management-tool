import { useState, useEffect } from 'react'
import { createPortal } from "react-dom";
import * as XLSX from 'xlsx'
function GlobalLists({ selectedCollection }) {
    const [collectionName, setCollectionName] = useState(
        selectedCollection || ''
    )
    const [globalLists, setGlobalLists] = useState([])
    const [listName, setListName] = useState('')
    const [configOpen, setConfigOpen] = useState(true)
    const [collections, setCollections] = useState([])
    const [collectionsError, setCollectionsError] = useState('')
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
    const [excelImportLoading, setExcelImportLoading] = useState(false)
    const [xmlImportLoading, setXmlImportLoading] = useState(false)
    const [mode, setMode] = useState('xml')
    const [importSource, setImportSource] = useState(null)
    const [xmlFileName, setXmlFileName] = useState('')
    const [excelFileName, setExcelFileName] = useState('')
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
    const exportGlobalListsToXml = async () => {
        try {
            const response = await fetch(
                `/global-lists?collection_name=${encodeURIComponent(collectionName)}`
            );
            const data = await response.json();
            if (!response.ok || !data.xml) {
                throw new Error(
                    data.detail || "GlobalLists XML alınamadı."
                );
            }
            const blob = new Blob(
                [data.xml],
                { type: "application/xml;charset=utf-8" }
            );
            const url = URL.createObjectURL(blob);
            const link = document.createElement("a");
            link.href = url;
            link.download = `GlobalLists-${collectionName}.xml`;
            document.body.appendChild(link);
            link.click();
            link.remove();
            URL.revokeObjectURL(url);
        } catch (error) {
            alert(error.message);
        }
    };
    const importGlobalListsFromXml = async (file) => {
        if (!file) return;
        if (xmlImportLoading || excelImportLoading || applyLoading) return;
        setXmlImportLoading(true);
        setXmlFileName(file.name);
        setPreviewResult(null);
        setImportSource(null);
        setError('');
        setApplyError('');
        setConfirmApply(false);
        try {
            const xmlContent = await file.text();
            const parser = new DOMParser();
            const xmlDoc = parser.parseFromString(
                xmlContent,
                "application/xml"
            );
            if (xmlDoc.querySelector("parsererror")) {
                throw new Error("XML dosyasının biçimi geçersiz.");
            }
            if (xmlDoc.documentElement.localName !== "GLOBALLISTS") {
                throw new Error(
                    "XML kök elemanı GLOBALLISTS olmalıdır."
                );
            }
            const response = await fetch(
                "/global-lists/preview-xml",
                {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json"
                    },
                    body: JSON.stringify({
                        collection_name: collectionName,
                        xml_content: xmlContent
                    })
                }
            );
            const data = await response.json();
            if (!response.ok || !data.success) {
                throw new Error(
                    typeof data.detail === "string"
                        ? data.detail
                        : "XML Preview oluşturulamadı."
                );
            }
            setPreviewResult(data);
            setImportSource('xml');
        } catch (error) {
            setError(`XML import failed: ${error.message}`);
        } finally {
            setXmlImportLoading(false);
        }
    };
    async function loadGlobalLists() {
        setLoading(true)
        setLoaded(false)
        setError('')
        setGlobalLists([])
        setListName('')
        setPreviewResult(null)
        setImportSource(null)
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
    function exportGlobalListsToExcel() {
        if (!loaded || globalLists.length === 0) {
            setError('Please load GlobalLists first.')
            return
        }
        const rows = globalLists.flatMap(list => {
            const values = list.values ?? []
            if (values.length === 0) {
                return [{
                    GlobalList: list.name,
                    Value: ''
                }]
            }
            return values.map(value => ({
                GlobalList: list.name,
                Value: value ?? ''
            }))
        })
        const worksheet = XLSX.utils.json_to_sheet(rows)
        worksheet['!cols'] = [
            { wch: 35 },
            { wch: 45 }
        ]
        const workbook = XLSX.utils.book_new()
        XLSX.utils.book_append_sheet(
            workbook,
            worksheet,
            'GlobalLists'
        )
        XLSX.writeFile(
            workbook,
            `GlobalLists\_${collectionName}.xlsx`
        )
    }
    function downloadGlobalListTemplate() {
        const worksheet = XLSX.utils.aoa_to_sheet([
            ['GlobalList', 'Operation', 'OldValue', 'NewValue']
        ])
        worksheet['!cols'] = [
            { wch: 25 },
            { wch: 18 },
            { wch: 25 },
            { wch: 25 }
        ]
        const workbook = XLSX.utils.book_new()
        XLSX.utils.book_append_sheet(
            workbook,
            worksheet,
            'GlobalList Changes'
        )
        XLSX.writeFile(
            workbook,
            'GlobalLists_Import_Template.xlsx'
        )
    }
    async function importGlobalListsFromExcel(file) {
        if (!file) return
        if (excelImportLoading || applyLoading) return
        setExcelImportLoading(true)
        setExcelFileName(file.name)
        setPreviewResult(null)
        setImportSource(null)
        setConfirmApply(false)
        setApplyError('')
        try {
            setError('')
            const buffer = await file.arrayBuffer()
            const workbook = XLSX.read(buffer, { type: 'array' })
            const worksheet = workbook.Sheets[workbook.SheetNames[0]]
            const rows = XLSX.utils.sheet_to_json(worksheet, {
                defval: ''
            })
            console.log('Excel rows:', rows)
            const items = rows.map((row, index) => {
                const operation = String(row.Operation ?? '').trim().toLowerCase()
                const item = {
                    list_name: String(row.GlobalList ?? '').trim(),
                    operation,
                    old_value: String(row.OldValue ?? '').trim(),
                    new_value: String(row.NewValue ?? '').trim()
                }
                if (!item.list_name || !['add', 'remove', 'update'].includes(operation)) {
                    throw new Error(`Excel satır ${index + 2}: Geçersiz GlobalList veya Operation.`)
                }
                if (
                    (operation === 'add' && !item.new_value) ||
                    (operation === 'remove' && !item.old_value) ||
                    (operation === 'update' && (!item.old_value || !item.new_value))
                ) {
                    throw new Error(`Excel satır ${index + 2}: Gerekli değer eksik.`)
                }
                return item
            })
            if (!collectionName) {
                throw new Error('Önce bir Collection seçmelisin.')
            }
            const response = await fetch('/global-lists/preview-bulk', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    collection_name: collectionName,
                    items: items
                })
            })
            const data = await response.json()
            if (!response.ok || !data.success) {
                throw new Error(
                    typeof data.detail === 'string'
                        ? data.detail
                        : 'Bulk Preview oluşturulamadı.'
                )
            }
            setPreviewResult(data)
            setImportSource('excel')
            console.log('Bulk Preview:', data)
        } catch (err) {
            setError(`Excel okunamadı: ${err.message}`)
        }
        finally {
            setExcelImportLoading(false)
        }
    }
    useEffect(() => {
        async function loadCollections() {
            try {
                const response = await fetch('/collections')
                if (!response.ok) {
                    throw new Error('Collection listesi alınamadı.')
                }
                const data = await response.json()
                // Backend'in dönüş biçimini destekle.
                const items = Array.isArray(data)
                    ? data
                    : data.collections ?? []
                const names = items
                    .map((item) =>
                        typeof item === 'string'
                            ? item
                            : item.name ?? item.Name
                    )
                    .filter(Boolean)
                setCollections(names)
                if (!selectedCollection && names.length > 0) {
                    setCollectionName((current) =>
                        names.includes(current) ? current : names[0]
                    )
                }
            } catch (err) {
                setCollectionsError(err.message)
            }
        }
        loadCollections()
    }, [selectedCollection])
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
        setImportSource(null)
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
        setImportSource(null)
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
        setImportSource(null)
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
            setImportSource('manual')
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
    function changeMode(nextMode) {
        if (applyLoading || xmlImportLoading || excelImportLoading || previewLoading) return
        setMode(nextMode)
        setPreviewResult(null)
        setImportSource(null)
        setConfirmApply(false)
        setApplyError('')
        setError('')
        setSelectedDiff(null)
    }

    return (
        <section>
            <p className="breadcrumb">MANAGEMENT / GLOBAL LISTS</p>
            <h1>GlobalLists</h1>
            <p>Manage Azure DevOps GlobalList values.</p>
            <div className="workspace-panel" style={{ padding: '22px', marginTop: 20 }}>
                <div style={{ marginBottom: 16 }}>
                    <h3 style={{ margin: '0 0 5px', fontSize: 16, color: '#0f172a' }}>Choose a management method</h3>
                    <p style={{ margin: 0, color: '#64748b', fontSize: 13 }}>Select how you want to manage your GlobalLists.</p>
                </div>
                <div role="group" aria-label="GlobalLists management method" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(190px, 1fr))', gap: 12 }}>
                    {[
                        { value: 'xml', icon: '</>', title: 'XML Management', description: 'Export, edit and import XML' },
                        { value: 'excel', icon: '▦', title: 'Excel Management', description: 'Manage bulk changes in Excel' },
                        { value: 'manual', icon: '✎', title: 'Manual Edit', description: 'Edit list values directly' }
                    ].map((option) => {
                        const active = mode === option.value
                        const disabled = applyLoading || xmlImportLoading || excelImportLoading || previewLoading
                        return (
                            <button
                                key={option.value}
                                type="button"
                                onClick={() => changeMode(option.value)}
                                disabled={disabled}
                                aria-pressed={active}
                                style={{
                                    position: 'relative', textAlign: 'left', display: 'flex', alignItems: 'flex-start', gap: 12,
                                    padding: '17px 15px', borderRadius: 12,
                                    border: `1.5px solid ${active ? '#2563eb' : '#e2e8f0'}`,
                                    background: active ? '#eff6ff' : '#fff',
                                    boxShadow: active ? '0 0 0 2px rgba(37,99,235,0.07)' : 'none',
                                    cursor: disabled ? 'not-allowed' : 'pointer',
                                    opacity: disabled ? 0.6 : 1,
                                    transition: 'background 150ms ease, border-color 150ms ease, box-shadow 150ms ease'
                                }}
                            >
                                <span aria-hidden="true" style={{
                                    width: 38, height: 38, flexShrink: 0, borderRadius: 10,
                                    display: 'grid', placeItems: 'center',
                                    background: active ? '#dbeafe' : '#f1f5f9',
                                    color: active ? '#1d4ed8' : '#475569',
                                    fontSize: option.value === 'xml' ? 13 : 21, fontWeight: 750
                                }}>{option.icon}</span>
                                <span style={{ display: 'block', paddingRight: 12 }}>
                                    <strong style={{ display: 'block', color: active ? '#1d4ed8' : '#0f172a', fontSize: 13, marginBottom: 5 }}>{option.title}</strong>
                                    <small style={{ display: 'block', color: '#64748b', fontSize: 11, lineHeight: 1.45 }}>{option.description}</small>
                                </span>
                                {active && <span aria-label="Selected" style={{ position: 'absolute', top: 10, right: 11, color: '#2563eb', fontSize: 16, fontWeight: 700 }}>✓</span>}
                            </button>
                        )
                    })}
                </div>
            </div>
            {mode !== 'manual' && (
                <div className="workspace-panel excel-management-card">
                    <div className="excel-card-header">
                        <div className="excel-card-icon">▦</div>
                        <div>
                            <h3>{mode === 'xml' ? 'XML Management' : 'Excel Management'}</h3>
                            <p>{mode === 'xml' ? 'Export, edit locally and import GlobalLists XML.' : 'Manage multiple GlobalList changes using Excel.'}</p>
                        </div>
                        <span className={`excel-status ${loaded ? 'ready' : 'waiting'}`}>
                            {loaded ? 'Ready' : 'Not loaded'}
                        </span>
                    </div>
                    <div className="excel-card-actions">
                        {mode === 'excel' && (<>
                            <button
                                type="button"
                                className="excel-action-btn excel-export-btn"
                                onClick={exportGlobalListsToExcel}
                                disabled={
                                    !loaded ||
                                    loading ||
                                    excelImportLoading ||
                                    applyLoading ||
                                    globalLists.length === 0
                                }
                            >
                                <span className="excel-action-icon">↓</span>
                                <span className="excel-action-content">
                                    <strong>Export to Excel</strong>
                                    <small>Download current GlobalLists</small>
                                </span>
                            </button>
                            <label
                                htmlFor="global-excel-import"
                                className={`excel-action-btn excel-import-btn ${!loaded || loading || globalLists.length === 0
                                    ? 'is-disabled'
                                    : ''
                                    }`}
                            >
                                <span className="excel-action-icon">↑</span>
                                <span className="excel-action-content">
                                    <strong>Import from Excel</strong>
                                    <small>Preview bulk changes</small>
                                </span>
                            </label>
                            <input
                                id="global-excel-import"
                                className="excel-file-input"
                                type="file"
                                accept=".xlsx,.xls"
                                disabled={!loaded || loading || globalLists.length === 0}
                                onChange={(event) => {
                                    const file = event.target.files?.[0]
                                    importGlobalListsFromExcel(file)
                                    event.target.value = ''
                                }}
                            />
                        </>)}
                        {mode === 'xml' && (<>
                            <button
                                type="button"
                                className="excel-action-btn excel-export-btn"
                                onClick={exportGlobalListsToXml}
                                disabled={!loaded || loading || applyLoading || xmlImportLoading || excelImportLoading}
                            >
                                <span className="excel-action-icon">↓</span>
                                <span className="excel-action-content">
                                    <strong>Export to XML</strong>
                                    <small>Download GlobalLists XML</small>
                                </span>
                            </button>
                            <label
                                htmlFor="global-xml-import"
                                className={`excel-action-btn excel-import-btn ${!loaded || loading || applyLoading
                                    ? 'is-disabled'
                                    : ''
                                    }`}
                            >
                                <span className="excel-action-icon">↑</span>
                                <span className="excel-action-content">
                                    <strong>Import from XML</strong>
                                    <small>Upload edited GlobalLists XML</small>
                                </span>
                            </label>
                            <input
                                id="global-xml-import"
                                className="excel-file-input"
                                type="file"
                                accept=".xml,application/xml,text/xml"
                                disabled={!loaded || loading || applyLoading || xmlImportLoading || excelImportLoading}
                                onChange={async (event) => {
                                    const file = event.target.files?.[0]
                                    if (file) {
                                        await importGlobalListsFromXml(file)
                                    }
                                    event.target.value = ''
                                }}
                            />
                        </>)}
                    </div>
                    {mode === 'excel' && (<div className="excel-template-row">
                        <button
                            type="button"
                            className="excel-template-link"
                            onClick={downloadGlobalListTemplate}
                        >
                            <span>↓</span>
                            Download Import Template
                        </button>
                    </div>)}
                    {xmlImportLoading && (
                        <div className="excel-import-feedback" role="status" aria-live="polite">
                            <span className="excel-loading-spinner" />
                            <div><strong>Processing XML file...</strong><p>Validating XML and preparing preview. Please wait.</p></div>
                        </div>
                    )}
                    {excelImportLoading && (
                        <div className="excel-import-feedback" role="status">
                            <span className="excel-loading-spinner" />
                            <div>
                                <strong>Processing Excel file...</strong>
                                <p>Reading file and preparing changes. Please wait.</p>
                            </div>
                        </div>
                    )}
                    {!excelImportLoading && !xmlImportLoading && importSource === mode &&
                        previewResult?.success &&
                        previewResult?.changes?.length > 0 && (
                            <div className="excel-import-feedback excel-import-ready" role="status">
                                <span className="excel-feedback-check">✓</span>
                                <div>
                                    <strong>{mode === 'xml' ? 'XML imported successfully for preview' : 'Excel imported successfully for preview'}</strong>
                                    <p>
                                        {mode === 'xml' ? xmlFileName : excelFileName} — {previewResult.total_changes} changes ready.
                                        No changes applied to Azure DevOps yet.
                                    </p>
                                </div>
                            </div>
                        )}
                    {!loaded && (
                        <div className="excel-card-notice">
                            Select a collection and load GlobalLists to enable file management.
                        </div>
                    )}
                    {importSource === mode && previewResult?.success &&
                        previewResult?.changes?.length > 0 && (
                            <div className="excel-preview-section">
                                <div className="excel-preview-heading">
                                    <h4>Import Preview</h4>
                                    <span>{previewResult.total_changes} changes</span>
                                </div>
                                <div className="excel-table-scroll">
                                    <table className="excel-preview-table">
                                        <thead>
                                            <tr>
                                                <th>GlobalList</th>
                                                <th>Operation</th>
                                                <th>Old Value</th>
                                                <th>New Value</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {previewResult.changes.map((change, index) => (
                                                <tr key={index}>
                                                    <td>{change.list_name}</td>
                                                    <td>
                                                        <span className={`excel-operation ${change.operation}`}>
                                                            {change.operation.toUpperCase()}
                                                        </span>
                                                    </td>
                                                    <td>{change.old_value || (change.operation === 'remove_list' ? (change.values || []).join(', ') : '—')}</td>
                                                    <td>{change.new_value || (change.operation === 'add_list' ? (change.values || []).join(', ') : '—')}</td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                                <p className="excel-preview-note">
                                    Preview only — no changes have been applied to Azure DevOps.
                                </p>
                                <div className="excel-apply-actions">
                                    <button
                                        type="button"
                                        className="excel-apply-btn"
                                        disabled={applyLoading || loading}
                                        onClick={() => {
                                            setApplyError('')
                                            setConfirmApply(true)
                                        }}
                                    >
                                        Apply {previewResult.total_changes} Changes
                                    </button>
                                </div>
                            </div>
                        )}
                </div>
            )}
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
                                    {collections.map((name) => (
                                        <option key={name} value={name}>
                                            {name}
                                        </option>
                                    ))}
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
            {mode === 'manual' && selectedList && (
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
            {mode === 'manual' && (<div className="field-operations">
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
                {importSource === 'manual' && previewResult && (
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
            )}
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
                        style={{ width: 'min(760px, 100%)', maxHeight: '90vh', overflowY: 'auto', borderRadius: 18, background: '#fff', color: '#172033', boxShadow: '0 25px 80px rgba(0,0,0,0.3)', padding: 30 }}
                    >
                        <div style={{ display: 'flex', gap: 14, alignItems: 'flex-start', marginBottom: 22 }}>
                            <div aria-hidden="true" style={{ width: 44, height: 44, flexShrink: 0, display: 'grid', placeItems: 'center', borderRadius: 12, background: '#fff4e5', color: '#b45309', fontSize: 24 }}>!</div>
                            <div>
                                <h2 id="global-apply-title" style={{ margin: '0 0 6px', fontSize: 21, fontWeight: 700 }}>Confirm Apply Changes</h2>
                                <p id="global-apply-description" style={{ margin: 0, color: '#64748b', lineHeight: 1.5 }}>Review the changes before importing them into Azure DevOps Server.</p>
                            </div>
                        </div>
                        <div className="global-confirm-details">
                            <div className="global-confirm-collection">
                                <span>Collection</span>
                                <strong>{collectionName}</strong>
                            </div>
                            {previewResult?.changes?.length > 0 ? (
                                <>
                                    <div className="global-confirm-summary">
                                        <strong>{importSource === 'xml' ? 'XML Import' : 'Excel Import'}</strong>
                                        <span>{previewResult.changes.length} changes</span>
                                    </div>
                                    <div className="global-confirm-table-wrap">
                                        <table className="excel-preview-table">
                                            <thead>
                                                <tr>
                                                    <th>GlobalList</th>
                                                    <th>Operation</th>
                                                    <th>Old Value</th>
                                                    <th>New Value</th>
                                                </tr>
                                            </thead>
                                            <tbody>
                                                {previewResult.changes.map((change, index) => (
                                                    <tr key={index}>
                                                        <td>{change.list_name}</td>
                                                        <td>
                                                            <span className={`excel-operation ${change.operation}`}>
                                                                {change.operation.toUpperCase()}
                                                            </span>
                                                        </td>
                                                        <td>{change.old_value || (change.operation === 'remove_list' ? (change.values || []).join(', ') : '—')}</td>
                                                        <td>{change.new_value || (change.operation === 'add_list' ? (change.values || []).join(', ') : '—')}</td>
                                                    </tr>
                                                ))}
                                            </tbody>
                                        </table>
                                    </div>
                                </>
                            ) : (
                                <>
                                    <div className="global-confirm-row">
                                        <span>GlobalList</span>
                                        <strong>{previewResult?.list_name || listName}</strong>
                                    </div>
                                    <div className="global-confirm-row">
                                        <span>Operation</span>
                                        <strong>{operation}</strong>
                                    </div>
                                    <div className="global-confirm-row">
                                        <span>Change</span>
                                        <strong>
                                            {operation === 'update'
                                                ? `${oldValue} → ${newValue}`
                                                : operation === 'add'
                                                    ? `+ ${itemValue}`
                                                    : `− ${itemValue}`}
                                        </strong>
                                    </div>
                                </>
                            )}
                        </div>
                        <div style={{ background: '#eff6ff', border: '1px solid #bfdbfe', borderRadius: 12, padding: '13px 15px', color: '#1e40af', lineHeight: 1.55, fontSize: 14 }}>
                            A backup will be created before import. This change affects the collection-level GlobalList and may impact projects that use it.
                        </div>
                        {applyError && <p role="alert" style={{ color: '#b91c1c' }}>{applyError}</p>}
                        <div style={{ display: 'flex', justifyContent: 'flex-end', flexWrap: 'wrap', gap: 12, marginTop: 26 }}>
                            <button
                                type="button"
                                disabled={applyLoading}
                                onClick={() => {
                                    setConfirmApply(false)
                                    setApplyError('')
                                }}
                                style={{
                                    border: '1px solid #cbd5e1',
                                    borderRadius: 9,
                                    background: '#fff',
                                    color: '#334155',
                                    padding: '11px 18px',
                                    fontWeight: 600,
                                    cursor: applyLoading ? 'not-allowed' : 'pointer'
                                }}
                            >
                                {applyLoading ? 'Import in progress' : 'Cancel'}
                            </button>
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
