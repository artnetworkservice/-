import { useEffect, useRef, useState } from 'react'
import { api } from './api'
import type { DocumentData, DocumentRecord, DocumentRow, Item, Quote, Source, Template } from './types'
import { blankDocument, blankItem, blankQuote } from './types'

type Page = 'documents' | 'editor' | 'templates'
const SUBJECT_PREFIX = 'ราคากลางจัดซื้อพัสดุ'

function subjectDetail(subject: string) {
  return subject.replace(/^ราคากลาง(?:งาน)?จัดซื้อ(?:พัสดุ)?\s*/, '').trimStart()
}

const templateFields: { key: string; label: string; rows?: number }[] = [
  { key: 'agency', label: 'ส่วนราชการ' },
  { key: 'intro', label: 'คำนำและคำสั่งแต่งตั้ง', rows: 7 },
  { key: 'prior_clause', label: 'ข้อความกรณีเคยซื้อ', rows: 6 },
  { key: 'no_prior_clause', label: 'ข้อความกรณีไม่เคยซื้อ', rows: 6 },
  { key: 'reference_announcement', label: 'ข้อความประกาศราคาอ้างอิง', rows: 4 },
  { key: 'closing', label: 'คำลงท้าย' },
  { key: 'signature_1', label: 'ผู้ลงชื่อคนที่ 1' },
  { key: 'signature_2', label: 'ผู้ลงชื่อคนที่ 2' },
  { key: 'signature_3', label: 'ผู้ลงชื่อคนที่ 3' },
]

function Icon({ name, size = 18 }: { name: 'file' | 'plus' | 'layers' | 'download' | 'eye' | 'trash' | 'copy' | 'search' | 'up' | 'down' | 'save' | 'edit' | 'database'; size?: number }) {
  const common = { width: size, height: size, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 1.8, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const, 'aria-hidden': true as const }
  const shapes: Record<string, React.ReactNode> = {
    file: <><path d="M6 3h8l4 4v14H6a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2Z"/><path d="M14 3v5h5M8 13h8M8 17h8"/></>,
    plus: <path d="M12 5v14M5 12h14"/>,
    layers: <><path d="m12 3 9 5-9 5-9-5 9-5Z"/><path d="m3 12 9 5 9-5M3 16l9 5 9-5"/></>,
    download: <><path d="M12 3v12m-4-4 4 4 4-4"/><path d="M4 17v3h16v-3"/></>,
    eye: <><path d="M2 12s3.6-6 10-6 10 6 10 6-3.6 6-10 6-10-6-10-6Z"/><circle cx="12" cy="12" r="2.5"/></>,
    trash: <><path d="M4 7h16M9 7V4h6v3m4 0-1 14H6L5 7"/><path d="M10 11v6m4-6v6"/></>,
    copy: <><rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h3"/></>,
    search: <><circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/></>,
    up: <path d="m5 14 7-7 7 7"/>, down: <path d="m5 10 7 7 7-7"/>,
    save: <><path d="M4 3h14l3 3v15H4V3Z"/><path d="M8 3v6h9V3M8 21v-8h9v8"/></>,
    edit: <><path d="m4 16 11-11 4 4-11 11-5 1 1-5Z"/><path d="m13 7 4 4"/></>,
    database: <><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5v7c0 1.7 4 3 9 3s9-1.3 9-3V5M3 12v7c0 1.7 4 3 9 3s9-1.3 9-3v-7"/></>,
  }
  return <svg {...common}>{shapes[name]}</svg>
}

function VendorInput({ value, onChange }: { value: string; onChange: (name: string) => void }) {
  const [suggestions, setSuggestions] = useState<string[]>([])
  const [focused, setFocused] = useState(false)
  useEffect(() => {
    if (!focused || value.trim().length < 2) { setSuggestions([]); return }
    const timer = window.setTimeout(() => {
      api.vendors(value).then(rows => setSuggestions(rows.map(row => row.name).filter(name => name !== value))).catch(() => setSuggestions([]))
    }, 180)
    return () => window.clearTimeout(timer)
  }, [value, focused])
  return <div className="vendor-input">
    <input value={value} onChange={event => onChange(event.target.value)} onFocus={() => setFocused(true)} onBlur={() => window.setTimeout(() => setFocused(false), 150)} placeholder="ชื่อบริษัทหรือร้านค้า" aria-label="ชื่อบริษัท" autoComplete="off" />
    {focused && suggestions.length > 0 && <div className="suggestions" role="listbox" aria-label="ชื่อบริษัทที่เคยใช้">
      {suggestions.map(name => <button type="button" role="option" aria-selected={false} key={name} onMouseDown={event => event.preventDefault()} onClick={() => { onChange(name); setFocused(false) }}>{name}</button>)}
    </div>}
  </div>
}

function formatDate(value: string) {
  if (!value) return '—'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat('th-TH', { day: 'numeric', month: 'short', year: 'numeric' }).format(date)
}

function numericOnly(value: string) {
  const clean = value.replace(/[^0-9๐-๙.]/g, '')
  const point = clean.indexOf('.')
  return point < 0 ? clean : clean.slice(0, point + 1) + clean.slice(point + 1).replace(/\./g, '')
}

function App() {
  const [page, setPage] = useState<Page>('documents')
  const [templates, setTemplates] = useState<Template[]>([])
  const [documents, setDocuments] = useState<DocumentRow[]>([])
  const [query, setQuery] = useState('')
  const [trash, setTrash] = useState(false)
  const [form, setForm] = useState<DocumentData | null>(null)
  const [documentId, setDocumentId] = useState<string | null>(null)
  const [archivedTemplateName, setArchivedTemplateName] = useState('')
  const [dirty, setDirty] = useState(false)
  const [saveStatus, setSaveStatus] = useState('ยังไม่บันทึก')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [previewId, setPreviewId] = useState<string | null>(null)
  const [selectedTemplateId, setSelectedTemplateId] = useState<string | null>(null)
  const [templateName, setTemplateName] = useState('')
  const [templateBlocks, setTemplateBlocks] = useState<Record<string, string>>({})
  const [templateVersions, setTemplateVersions] = useState<{ id: string; version: number; created_at: string }[]>([])
  const [validationTotal, setValidationTotal] = useState<string | null>(null)
  const restoreRef = useRef<HTMLInputElement>(null)
  const importRef = useRef<HTMLInputElement>(null)

  const refreshTemplates = async () => {
    const rows = await api.templates()
    setTemplates(rows)
    return rows
  }
  const refreshDocuments = async (search = query, showTrash = trash) => setDocuments(await api.documents(search, showTrash))

  useEffect(() => {
    refreshTemplates().catch(exc => setError(exc.message))
    api.documents().then(setDocuments).catch(exc => setError(exc.message))
  }, [])
  useEffect(() => {
    if (page !== 'documents') return
    const timer = window.setTimeout(() => refreshDocuments(query, trash).catch(exc => setError(exc.message)), 220)
    return () => window.clearTimeout(timer)
  }, [query, trash, page])
  useEffect(() => {
    if (!dirty || !documentId || !form) return
    const timer = window.setTimeout(() => {
      const snapshot = form
      setSaveStatus('กำลังบันทึก…')
      api.saveDocument(snapshot, documentId)
        .then(() => { setDirty(false); setSaveStatus('บันทึกอัตโนมัติแล้ว') })
        .catch(exc => { setSaveStatus('บันทึกไม่สำเร็จ'); setError(exc.message) })
    }, 1200)
    return () => window.clearTimeout(timer)
  }, [dirty, form, documentId])

  const startNew = () => {
    if (!templates.length) { setError('ยังไม่มีแม่แบบ'); return }
    setForm(blankDocument(templates[0].id))
    setDocumentId(null)
    setArchivedTemplateName('')
    setDirty(false)
    setValidationTotal(null)
    setSaveStatus('ยังไม่บันทึก')
    setError('')
    setPage('editor')
  }
  const openDocument = async (id: string) => {
    try {
      const record = await api.document(id)
      setForm({ ...record.data, items: record.data.items.map(item => item.prior?.document_date ? {
        ...item, prior: { ...item.prior, document_number: `${item.prior.document_number} ลง ${formatDate(item.prior.document_date)}`, document_date: '' },
      } : item) })
      setDocumentId(record.id)
      setArchivedTemplateName(record.template_name)
      setDirty(false)
      setValidationTotal(null)
      setSaveStatus('บันทึกแล้ว')
      setError('')
      setPage('editor')
    } catch (exc) { setError((exc as Error).message) }
  }
  const changeForm = (update: (value: DocumentData) => DocumentData) => {
    setForm(current => current ? update(current) : current)
    setDirty(true)
    setSaveStatus('มีข้อมูลที่ยังไม่บันทึก')
    setValidationTotal(null)
  }
  const field = (key: keyof Omit<DocumentData, 'items'>, value: string) => changeForm(current => ({ ...current, [key]: value }))
  const updateItem = (index: number, update: (item: Item) => Item) => changeForm(current => ({ ...current, items: current.items.map((item, position) => position === index ? update(item) : item) }))
  const updateQuote = (itemIndex: number, quoteIndex: number, update: (quote: Quote) => Quote) => updateItem(itemIndex, item => ({ ...item, quotes: item.quotes.map((quote, position) => position === quoteIndex ? update(quote) : quote) }))
  const addItem = () => changeForm(current => ({ ...current, items: [...current.items, blankItem(current.items[0]?.quotes.map(quote => quote.company).filter(Boolean) || [])] }))
  const duplicateItem = (index: number) => changeForm(current => {
    const source = current.items[index]
    const item: Item = { ...source, name: source.name, prior: { ...source.prior, unit_price: '' }, reference: { ...source.reference, unit_price: '' }, quotes: source.quotes.map(quote => blankQuote(quote.company)) }
    const items = [...current.items]; items.splice(index + 1, 0, item)
    return { ...current, items }
  })
  const removeItem = (index: number) => {
    if (!form || form.items.length === 1) return setError('ต้องมีอย่างน้อย 1 รายการ')
    changeForm(current => ({ ...current, items: current.items.filter((_, position) => position !== index) }))
  }
  const moveItem = (index: number, direction: -1 | 1) => changeForm(current => {
    const next = [...current.items]
    const other = index + direction
    if (other < 0 || other >= next.length) return current
    ;[next[index], next[other]] = [next[other], next[index]]
    return { ...current, items: next }
  })

  const save = async (): Promise<DocumentRecord | null> => {
    if (!form) return null
    try {
      setBusy(true); setError(''); setSaveStatus('กำลังบันทึก…')
      const result = await api.saveDocument(form, documentId || undefined)
      setDocumentId(result.id)
      setDirty(false)
      setSaveStatus('บันทึกแล้ว')
      return result
    } catch (exc) { setError((exc as Error).message); setSaveStatus('บันทึกไม่สำเร็จ'); return null }
    finally { setBusy(false) }
  }
  const validate = async () => {
    if (!form) return false
    try {
      setError('')
      const result = await api.validate(form)
      setValidationTotal(result.total)
      return true
    } catch (exc) { setError((exc as Error).message); setValidationTotal(null); return false }
  }
  const exportFile = async (format: 'docx' | 'pdf', preview = false) => {
    if (!(await validate())) return
    const record = await save()
    if (!record) return
    if (preview) await openPreview(record.id)
    else await downloadFile(record.id, format, record.subject)
  }
  const downloadFile = async (id: string, format: 'docx' | 'pdf', subject: string) => {
    try {
      setBusy(true); setError('')
      const blob = await api.exportBlob(id, format)
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = `${subject.replace(/[\\/:*?"<>|]/g, '-').slice(0, 80)}.${format}`
      document.body.appendChild(anchor)
      anchor.click()
      anchor.remove()
      window.setTimeout(() => URL.revokeObjectURL(url), 1000)
    } catch (exc) { setError((exc as Error).message) }
    finally { setBusy(false) }
  }
  const openPreview = async (id: string) => {
    try {
      setBusy(true); setError('')
      await api.exportBlob(id, 'pdf')
      setPreviewId(id)
    } catch (exc) { setError((exc as Error).message) }
    finally { setBusy(false) }
  }
  const selectTemplate = async (id: string, rows = templates) => {
    const record = rows.find(row => row.id === id)
    if (!record) return
    setSelectedTemplateId(id); setTemplateName(record.name); setTemplateBlocks({ ...record.blocks })
    setTemplateVersions(await api.templateVersions(id))
  }
  const saveTemplate = async () => {
    if (!selectedTemplateId) return
    try {
      setBusy(true); setError('')
      await api.updateTemplate(selectedTemplateId, templateName, templateBlocks)
      const rows = await refreshTemplates(); await selectTemplate(selectedTemplateId, rows)
      window.alert('บันทึกแม่แบบเป็นเวอร์ชั่นใหม่แล้ว')
    } catch (exc) { setError((exc as Error).message) }
    finally { setBusy(false) }
  }
  const copyTemplate = async () => {
    const baseId = selectedTemplateId || templates[0]?.id
    if (!baseId) return
    const name = window.prompt('ชื่อแม่แบบใหม่', 'สำเนาแม่แบบราคากลาง')
    if (!name?.trim()) return
    try {
      const result = await api.createTemplate(name.trim(), baseId)
      const rows = await refreshTemplates(); await selectTemplate(result.id, rows)
    } catch (exc) { setError((exc as Error).message) }
  }
  const importTemplate = async (file: File) => {
    if (!file.name.toLowerCase().endsWith('.docx')) return setError('กรุณาเลือกไฟล์ Word .docx')
    try {
      setBusy(true); setError('')
      const dataUrl = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader()
        reader.onload = () => resolve(String(reader.result))
        reader.onerror = () => reject(new Error('อ่านไฟล์แม่แบบไม่สำเร็จ'))
        reader.readAsDataURL(file)
      })
      const result = await api.importTemplate(file.name.replace(/\.docx$/i, ''), dataUrl.split(',')[1])
      const rows = await refreshTemplates(); await selectTemplate(result.id, rows)
    } catch (exc) { setError((exc as Error).message) }
    finally { setBusy(false); if (importRef.current) importRef.current.value = '' }
  }
  const deleteTemplate = async () => {
    if (!selectedTemplateId || !window.confirm('ลบแม่แบบนี้ออกจากรายการ? เอกสารเดิมยังเปิดและดาวน์โหลดได้')) return
    try {
      setBusy(true); setError('')
      await api.deleteTemplate(selectedTemplateId)
      const rows = await refreshTemplates()
      setSelectedTemplateId(null)
      if (rows[0]) await selectTemplate(rows[0].id, rows)
    } catch (exc) { setError((exc as Error).message) }
    finally { setBusy(false) }
  }

  return <div className="app-shell">
    <header className="topbar"><div className="brand-mark" aria-hidden="true"><Icon name="file" size={27}/></div><div className="brand-name">ระบบออกใบราคากลาง<small>Version 1.1 · พัฒนาโดยทีม THEEKRIT | ธีร์กฤติ โซลูชั่น</small></div><div className="topbar-spacer"/><span className="topbar-caption">ข้อมูลเก็บในเครื่องนี้</span><span className="topbar-dot"/></header>
    <aside className="sidebar" aria-label="เมนูหลัก">
      <button className={page === 'documents' ? 'nav active' : 'nav'} onClick={() => { setPage('documents'); setError('') }}><Icon name="file"/>เอกสาร</button>
      <button className={page === 'editor' ? 'nav active' : 'nav'} onClick={startNew}><Icon name="plus"/>สร้างเอกสาร</button>
      <button className={page === 'templates' ? 'nav active' : 'nav'} onClick={() => { setPage('templates'); setError(''); if (!selectedTemplateId && templates[0]) selectTemplate(templates[0].id) }}><Icon name="layers"/>แม่แบบ</button>
      <div className="sidebar-bottom"><button className="nav" onClick={() => window.location.href = '/api/backup'}><Icon name="database"/>สำรองข้อมูล</button><button className="nav" onClick={() => restoreRef.current?.click()}><Icon name="download"/>กู้คืนข้อมูล</button><input ref={restoreRef} type="file" accept=".zip,application/zip" hidden onChange={async event => { const file = event.target.files?.[0]; if (!file || !window.confirm('การกู้คืนจะแทนที่ข้อมูลปัจจุบัน ต้องการดำเนินการหรือไม่?')) return; try { await api.restoreBackup(file); window.location.reload() } catch (exc) { setError((exc as Error).message) } }} /></div>
    </aside>
    <main className="main">
      {error && <div className="error-banner" role="alert"><strong>ตรวจสอบข้อมูล</strong><span>{error}</span><button onClick={() => setError('')} aria-label="ปิดข้อความ">×</button></div>}

      {page === 'documents' && <div className="page-content"><div className="page-heading"><div><h1>จัดการเอกสาร</h1><p>ค้นหา เปิดแก้ไข คัดลอก และดาวน์โหลดเอกสารที่บันทึกไว้</p></div><button className="button primary" onClick={startNew}><Icon name="plus"/>สร้างเอกสาร</button></div>
        <div className="toolbar"><label className="search-field"><Icon name="search"/><input value={query} onChange={event => setQuery(event.target.value)} placeholder="ค้นหาเรื่อง เลขที่ วันที่ หรือบริษัท" aria-label="ค้นหาเอกสาร" /></label><label className="trash-toggle"><input type="checkbox" checked={trash} onChange={event => setTrash(event.target.checked)}/>แสดงถังขยะ</label></div>
        <div className="table-wrap"><table className="document-table"><thead><tr><th>เรื่อง</th><th>แม่แบบ</th><th>ที่</th><th>วันที่</th><th>แก้ไขล่าสุด</th><th className="actions-head">การดำเนินการ</th></tr></thead><tbody>{documents.map(row => <tr key={row.id}><td><button className="text-link subject-cell" onClick={() => openDocument(row.id)}>{row.subject}</button>{row.deleted_at && <span className="muted small">ในถังขยะ</span>}</td><td>{row.template_name}</td><td>{row.document_number || '—'}</td><td>{formatDate(row.document_date)}</td><td>{formatDate(row.updated_at)}</td><td><div className="row-actions">{row.deleted_at ? <button title="กู้คืน" onClick={async () => { await api.restore(row.id); refreshDocuments() }}>กู้คืน</button> : <><button title="แก้ไข" onClick={() => openDocument(row.id)}><Icon name="edit"/></button><button title="ดูตัวอย่าง" onClick={() => openPreview(row.id)}><Icon name="eye"/></button><button title="คัดลอกเอกสาร" onClick={async () => { try { const copy = await api.duplicate(row.id); await refreshDocuments(); openDocument(copy.id) } catch (exc) { setError((exc as Error).message) } }}><Icon name="copy"/></button><button title="ดาวน์โหลด Word" onClick={() => downloadFile(row.id, 'docx', row.subject)}><Icon name="download"/><span>Word</span></button><button title="ดาวน์โหลด PDF" onClick={() => downloadFile(row.id, 'pdf', row.subject)}><span>PDF</span></button><button title="ย้ายไปถังขยะ" onClick={async () => { if (!window.confirm('ย้ายเอกสารนี้ไปถังขยะ?')) return; await api.delete(row.id); refreshDocuments() }}><Icon name="trash"/></button></>}</div></td></tr>)}</tbody></table>{documents.length === 0 && <div className="empty-state"><Icon name="file" size={30}/><h2>{trash ? 'ถังขยะว่าง' : 'ยังไม่มีเอกสาร'}</h2><p>{trash ? 'เอกสารที่ลบจะอยู่ที่นี่' : 'เริ่มสร้างเอกสารแรกจากแม่แบบที่เตรียมไว้'}</p>{!trash && <button className="button primary" onClick={startNew}>สร้างเอกสาร</button>}</div>}</div>
      </div>}

      {page === 'editor' && form && <div className="editor-layout"><div className="stepbar"><span><b>1</b> ข้อมูลเอกสาร</span><i/><span><b>2</b> รายการจัดซื้อ</span><i/><span><b>3</b> ตรวจทาน</span></div>
        <div className="editor-scroll"><section className="panel" id="document-info"><div className="panel-heading"><h1>{documentId ? 'แก้ไขเอกสาร' : 'สร้างเอกสารใหม่'}</h1><span className="save-indicator">{saveStatus}</span></div><div className="fields-grid"><label className="field"><span>แม่แบบ</span><select value={form.template_id} onChange={event => field('template_id', event.target.value)} disabled={Boolean(documentId)}>{!templates.some(row => row.id === form.template_id) && <option value={form.template_id}>{archivedTemplateName || "แม่แบบเดิม"} (ลบจากรายการแล้ว)</option>}{templates.map(row => <option key={row.id} value={row.id}>{row.name} (เวอร์ชั่น {row.version})</option>)}</select></label><label className="field"><span>ที่</span><input value={form.document_number} onChange={event => field('document_number', event.target.value)} placeholder="เลขที่เอกสาร" /></label><label className="field"><span>เรื่อง <em>*</em></span><div className="subject-composer"><span>{SUBJECT_PREFIX}</span><input aria-label="รายละเอียดเรื่อง" value={subjectDetail(form.subject)} onChange={event => { const detail = event.target.value.trimStart(); field('subject', detail ? `${SUBJECT_PREFIX} ${detail}` : '') }} placeholder="ระบุข้อความต่อท้าย" /></div></label><label className="field"><span>วันที่</span><input type="text" value={form.date} onChange={event => field('date', event.target.value)} placeholder="เช่น ๑๗ ก.ย. ๖๙" /></label></div></section>
          <section className="panel items-panel"><div className="panel-heading"><div><h2>รายการจัดซื้อ</h2><p>{form.items.length} รายการ · ชื่อบริษัทของรายการใหม่จะดึงจากรายการที่ 1 โดยไม่คัดลอกราคา</p></div></div>
            <div className="item-stack">{form.items.map((item, index) => <article className="item-card" key={index}><div className="item-heading"><h3>รายการที่ {index + 1}</h3><div className="item-tools"><button title="เลื่อนขึ้น" aria-label={`เลื่อนรายการที่ ${index + 1} ขึ้น`} disabled={index === 0} onClick={() => moveItem(index, -1)}><Icon name="up"/></button><button title="เลื่อนลง" aria-label={`เลื่อนรายการที่ ${index + 1} ลง`} disabled={index === form.items.length - 1} onClick={() => moveItem(index, 1)}><Icon name="down"/></button><button title="คัดลอกรายการโดยล้างราคา" aria-label={`คัดลอกรายการที่ ${index + 1}`} onClick={() => duplicateItem(index)}><Icon name="copy"/></button><button title="ลบรายการ" aria-label={`ลบรายการที่ ${index + 1}`} onClick={() => removeItem(index)}><Icon name="trash"/></button></div></div>
              <div className="item-body"><div className="item-fields"><label className="field name-field"><span>รายละเอียดพัสดุ <em>*</em></span><input value={item.name} onChange={event => updateItem(index, current => ({ ...current, name: event.target.value }))} placeholder="ชื่อพัสดุ ขนาด และคุณลักษณะ" /></label><label className="field qty-field"><span>จำนวน <em>*</em></span><input inputMode="decimal" value={item.quantity} onChange={event => updateItem(index, current => ({ ...current, quantity: numericOnly(event.target.value), reference: { ...current.reference, quantity: numericOnly(event.target.value) } }))} /></label><label className="field unit-field"><span>หน่วย <em>*</em></span><input value={item.unit} onChange={event => updateItem(index, current => ({ ...current, unit: event.target.value }))} placeholder="เช่น กล่อง" /></label></div>
                <div className="source-options"><label><input type="checkbox" checked={item.source === 'prior'} onChange={event => updateItem(index, current => ({ ...current, source: event.target.checked ? 'prior' : 'market' as Source }))}/>เคยสั่งซื้อ</label><label><input type="checkbox" checked={item.source === 'reference'} onChange={event => updateItem(index, current => ({ ...current, source: event.target.checked ? 'reference' : 'market' as Source, reference: { ...current.reference, quantity: current.quantity } }))}/>มีราคาอ้างอิง</label></div>
                {item.source === 'prior' && <div className="conditional-area"><div className="subheading">ข้อมูลการซื้อครั้งก่อน</div><div className="prior-grid"><label className="field"><span>เลขที่เอกสารและวันที่เอกสาร <em>*</em></span><input value={item.prior.document_number} onChange={event => updateItem(index, current => ({ ...current, prior: { ...current.prior, document_number: event.target.value, document_date: '' } }))} placeholder="เช่น ๑๘๔๑/๖๘ ลง ๑๑ ก.ย. ๖๘" /></label><label className="field"><span>ราคาเดิมต่อหน่วย (บาท) <em>*</em></span><input inputMode="decimal" value={item.prior.unit_price} onChange={event => updateItem(index, current => ({ ...current, prior: { ...current.prior, unit_price: numericOnly(event.target.value) } }))} placeholder="0.00"/></label><label className="field"><span>จำนวนครั้งก่อน</span><input inputMode="decimal" value={item.prior.quantity} onChange={event => updateItem(index, current => ({ ...current, prior: { ...current.prior, quantity: numericOnly(event.target.value) } }))} placeholder="ถ้ามี"/></label></div></div>}
                {item.source === 'reference' ? <div className="conditional-area reference-area"><div className="subheading">ราคาอ้างอิง</div><div className="prior-grid"><label className="field"><span>ราคาต่อหน่วย (บาท) <em>*</em></span><input inputMode="decimal" value={item.reference.unit_price} onChange={event => updateItem(index, current => ({ ...current, reference: { ...current.reference, unit_price: numericOnly(event.target.value) } }))} placeholder="0.00" /></label><label className="field"><span>จำนวน</span><input value={item.quantity} disabled aria-label="จำนวนราคาอ้างอิง" /></label></div><p className="hint">รายการราคาอ้างอิงไม่ต้องกรอกบริษัท ระบบใช้ข้อความประกาศที่ตั้งไว้ในแม่แบบ</p></div> : <div className="quotes-area"><div className="subheading">ข้อมูลราคาจากผู้ขาย <span>{item.quotes.length} ราย</span></div><div className="quotes-table"><div className="quotes-head"><span>ลำดับ</span><span>ชื่อบริษัท / ร้านค้า</span><span>ราคาต่อหน่วย (บาท)</span><span></span></div>{item.quotes.map((quote, quoteIndex) => <div className="quote-row" key={quoteIndex}><span className="quote-number">{quoteIndex + 1}</span><VendorInput value={quote.company} onChange={name => updateQuote(index, quoteIndex, current => ({ ...current, company: name }))}/><input inputMode="decimal" value={quote.unit_price} onChange={event => updateQuote(index, quoteIndex, current => ({ ...current, unit_price: numericOnly(event.target.value) }))} placeholder="0.00" aria-label={`ราคาต่อหน่วยบริษัทที่ ${quoteIndex + 1}`} /><button title="ลบบริษัท" aria-label={`ลบบริษัทที่ ${quoteIndex + 1}`} onClick={() => updateItem(index, current => ({ ...current, quotes: current.quotes.filter((_, position) => position !== quoteIndex) }))}><Icon name="trash"/></button></div>)}</div><button className="button subtle" onClick={() => updateItem(index, current => ({ ...current, quotes: [...current.quotes, blankQuote()] }))}><Icon name="plus"/>เพิ่มบริษัท</button></div>}
              </div></article>)}</div><button className="add-item" onClick={addItem}><Icon name="plus"/>เพิ่มรายการ</button></section>
          <section className="review-strip"><div><h2>ตรวจทานก่อนส่งออก</h2><p>ระบบจะตรวจราคา เลขข้อ และสร้างหน้าเอกสารจริงก่อนดาวน์โหลด</p></div><div className="review-total">{validationTotal ? `${Number(validationTotal).toLocaleString('th-TH', { minimumFractionDigits: 2 })} บาท` : 'ยังไม่ตรวจราคา'}</div><button className="button subtle" onClick={validate}>ตรวจข้อมูล</button></section>
        </div><div className="editor-footer"><button className="button" onClick={save} disabled={busy}><Icon name="save"/>บันทึกฉบับร่าง</button><div className="footer-spacer"/><button className="button subtle" onClick={() => exportFile('pdf', true)} disabled={busy}><Icon name="eye"/>ดูตัวอย่าง</button><button className="button subtle" onClick={() => exportFile('docx')} disabled={busy}><Icon name="download"/>Word</button><button className="button primary" onClick={() => exportFile('pdf')} disabled={busy}><Icon name="download"/>PDF</button></div></div>}

      {page === 'templates' && <div className="page-content"><div className="page-heading"><div><h1>จัดการแม่แบบ</h1><p>แก้ข้อความคงที่และเงื่อนไขของแม่แบบ พร้อมเก็บเวอร์ชั่นเดิมไว้</p></div><div className="heading-actions"><button className="button" onClick={() => importRef.current?.click()} disabled={busy}><Icon name="download"/>นำเข้า Word</button><input ref={importRef} type="file" accept=".docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document" hidden onChange={event => { const file = event.target.files?.[0]; if (file) importTemplate(file) }}/><button className="button primary" onClick={copyTemplate}><Icon name="plus"/>เพิ่มจากแม่แบบเดิม</button></div></div><div className="template-layout"><div className="template-list">{templates.map(row => <button key={row.id} className={selectedTemplateId === row.id ? 'selected' : ''} onClick={() => selectTemplate(row.id)}><strong>{row.name}</strong><span>เวอร์ชั่น {row.version}</span></button>)}</div><div className="template-editor">{selectedTemplateId ? <><div className="template-header"><div><h2>แก้ไขแม่แบบ</h2><p>การบันทึกจะสร้างเวอร์ชั่นใหม่ เอกสารเก่าจะยังใช้เวอร์ชั่นเดิม</p></div><button className="button danger" disabled={busy} onClick={deleteTemplate}><Icon name="trash"/>ลบแม่แบบ</button></div><label className="field"><span>ชื่อแม่แบบ</span><input value={templateName} onChange={event => setTemplateName(event.target.value)}/></label><div className="template-fields">{templateFields.map(field => <label className="field" key={field.key}><span>{field.label}</span><textarea rows={field.rows || 2} value={templateBlocks[field.key] || ''} onChange={event => setTemplateBlocks(current => ({ ...current, [field.key]: event.target.value }))}/></label>)}</div><div className="template-actions"><button className="button primary" disabled={busy} onClick={saveTemplate}><Icon name="save"/>บันทึกเวอร์ชั่นใหม่</button><label className="field version-select"><span>ย้อนกลับเวอร์ชั่น</span><select value="" onChange={async event => { const id = event.target.value; if (!id || !window.confirm('เปิดใช้เวอร์ชั่นนี้แทนเวอร์ชั่นปัจจุบัน?')) return; await api.activateTemplateVersion(selectedTemplateId, id); const rows = await refreshTemplates(); selectTemplate(selectedTemplateId, rows) }}><option value="">เลือกเวอร์ชั่น</option>{templateVersions.map(row => <option key={row.id} value={row.id}>เวอร์ชั่น {row.version} · {formatDate(row.created_at)}</option>)}</select></label></div><p className="hint">แก้ไขข้อความและสร้างแม่แบบใหม่จากต้นแบบได้ที่นี่ การจัดหน้า DOCX ขั้นสูงยังต้องแก้ไฟล์ต้นฉบับ</p></> : <p>เลือกแม่แบบด้านซ้าย</p>}</div></div></div>}
    </main>
    {previewId && <div className="modal-backdrop" onClick={() => setPreviewId(null)}><div className="preview-modal" role="dialog" aria-modal="true" aria-label="ดูตัวอย่างเอกสาร" onClick={event => event.stopPropagation()}><div className="preview-header"><strong>ดูตัวอย่างเอกสาร</strong><div><a className="button subtle" href={api.exportUrl(previewId, 'docx')}>Word</a><a className="button subtle" href={api.exportUrl(previewId, 'pdf')}>PDF</a><button className="button" onClick={() => setPreviewId(null)}>ปิด</button></div></div><iframe title="ตัวอย่าง PDF" src={api.exportUrl(previewId, 'pdf', true)}/></div></div>}
  </div>
}

export default App
