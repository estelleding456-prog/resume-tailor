import { useEffect, useRef, useState } from 'react'
import type { PointerEvent as ReactPointerEvent } from 'react'

type Health = { status: string; service: string }
type Message = { role: 'user' | 'assistant'; content: string }
type ResumeItem = { date: string; heading: string; subheading: string; body: string[] }
type ResumeSection = { title: string; items: ResumeItem[]; paragraphs: string[] }
type ResumeStructured = { header: { name: string; contact: string }; sections: ResumeSection[] }
type ResumeAsset = { name: string; data_url: string; width?: number; height?: number }
type ParsedResume = { filename: string; format: string; parsed: { text: string; warnings?: string[]; structured?: ResumeStructured; assets?: ResumeAsset[] } }
type ModelConfig = { base_url: string; model_name: string; api_key: string }
type TemplateConfig = { font_size: number; name_font_size?: number; section_font_size?: number; font_family?: string; line_height: number; margin_top: number; margin_right: number; margin_bottom: number; margin_left: number; section_margin?: number; item_margin?: number; para_margin?: number; photo_width_mm?: number; photo_height_mm?: number; photo_rect_pct?: { left: number; top: number; width: number; height: number } }
type Preferences = { page_limit: 'one' | 'two' | 'unlimited'; structure_mode: 'preserve' | 'reorder' | 'rebuild'; layout_mode: 'preserve' | 'adaptive'; date_order: 'desc' | 'asc' | 'relevance'; profile_text: string; calibrated: boolean }

const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000'
const DEFAULT_PREFERENCES: Preferences = { page_limit: 'one', structure_mode: 'reorder', layout_mode: 'adaptive', date_order: 'desc', profile_text: '', calibrated: false }

function copyResume(value: ResumeStructured): ResumeStructured { return JSON.parse(JSON.stringify(value)) as ResumeStructured }

function EditableText({ value, editable, onCommit, className }: { value: string; editable: boolean; onCommit: (value: string) => void; className?: string }) {
  return <span className={className} contentEditable={editable} suppressContentEditableWarning onBlur={(event) => { if (editable && event.currentTarget.textContent !== value) onCommit(event.currentTarget.textContent ?? '') }}>{value}</span>
}

function renderPlain(text: string): string {
  return String(text ?? '')
    .replace(/```[\s\S]*?```/g, (m) => m.replace(/```/g, '').trim())
    .replace(/^---+$/gm, '')
    .replace(/\*\*([^*]+)\*\*/g, '$1')
    .replace(/\*([^*\s][^*]*)\*/g, '$1')
    .replace(/^\s*[-*•]\s+/gm, '')
    .replace(/^\s*#+\s+/gm, '')
}

function EditableLine({ value, editable, onCommit }: { value: string; editable: boolean; onCommit: (value: string) => void }) {
  const clean = value.replace(/^\*\*([^*]+)\*\*([：:])/, '$1$2')
  const match = clean.match(/^([^：:]{2,10})([：:])(.*)$/)
  return <span contentEditable={editable} suppressContentEditableWarning onBlur={(event) => { if (editable && event.currentTarget.textContent !== clean) onCommit(event.currentTarget.textContent ?? '') }}>{match ? <><strong>{match[1]}{match[2]}</strong>{match[3]}</> : clean}</span>
}

function ResumePaper({ structured, assets, template, editable, onChange }: { structured: ResumeStructured | null; assets: ResumeAsset[]; template: TemplateConfig; editable: boolean; onChange: (next: ResumeStructured) => void }) {
  if (!structured) return <div className="paper-placeholder"><span>上传简历后将在这里预览</span></div>
  const change = (mutate: (next: ResumeStructured) => void) => { const next = copyResume(structured); mutate(next); onChange(next) }
  const style = { fontSize: `${template.font_size}pt`, lineHeight: template.line_height, padding: `${template.margin_top}mm ${template.margin_right}mm ${template.margin_bottom}mm ${template.margin_left}mm`, fontFamily: template.font_family?.replace('MicrosoftYaHei', 'Microsoft YaHei') }
  const pw = template.photo_width_mm ?? 22
  const ph = template.photo_height_mm ?? 29
  return <article className="resume-paper" style={style}>
    <header className="resume-header"><div className="resume-text"><h2 style={{ fontSize: `${template.name_font_size ?? 18}pt` }}><EditableText value={structured.header.name} editable={editable} onCommit={(v) => change((n) => { n.header.name = v })} /></h2><p><EditableText value={structured.header.contact} editable={editable} onCommit={(v) => change((n) => { n.header.contact = v })} /></p></div>{assets[0] && <img className="resume-photo" style={{ width: `${pw}mm`, height: `${ph}mm` }} src={assets[0].data_url} alt="简历照片" />}</header>
    {structured.sections.map((section, si) => <section className="resume-section" key={`${section.title}-${si}`}>
      <h3 style={{ fontSize: `${template.section_font_size ?? 12}pt` }}><EditableText value={section.title} editable={editable} onCommit={(v) => change((n) => { n.sections[si].title = v })} /></h3>
      {section.paragraphs.map((paragraph, pi) => <p key={`${pi}-${paragraph}`}><EditableLine value={paragraph} editable={editable} onCommit={(v) => change((n) => { n.sections[si].paragraphs[pi] = v })} /></p>)}
      {section.items.map((item, ii) => <div className="resume-item" key={`${item.date}-${ii}`}><div className={`resume-item-head${item.heading && !item.subheading ? ' compact' : ''}`}>
        {item.heading && !item.subheading ? <><strong><EditableText value={item.date} editable={editable} onCommit={(v) => change((n) => { n.sections[si].items[ii].date = v })} /></strong><span><EditableText value={item.heading} editable={editable} onCommit={(v) => change((n) => { n.sections[si].items[ii].heading = v })} /></span></> : (['date', 'heading', 'subheading'] as const).map((field) => <strong key={field}><EditableText value={item[field]} editable={editable} onCommit={(v) => change((n) => { n.sections[si].items[ii][field] = v })} /></strong>)}
      </div>{item.body.map((line, bi) => <p key={`${bi}-${line}`}><EditableLine value={line} editable={editable} onCommit={(v) => change((n) => { n.sections[si].items[ii].body[bi] = v })} /></p>)}</div>)}
    </section>)}
  </article>
}

export default function App() {
  const [health, setHealth] = useState<Health | null>(null)
  const [leftWidth, setLeftWidth] = useState(36)
  const [topHeight, setTopHeight] = useState(50)
  const [dragging, setDragging] = useState<'vertical' | 'horizontal' | null>(null)
  const [message, setMessage] = useState('')
  const [chat, setChat] = useState<Message[]>([])
  const [resume, setResume] = useState<ParsedResume | null>(null)
  const [originalFileUrl, setOriginalFileUrl] = useState('')
  const [structured, setStructured] = useState<ResumeStructured | null>(null)
  const [assets, setAssets] = useState<ResumeAsset[]>([])
  const [resumeVersionId, setResumeVersionId] = useState('')
  const [versionName, setVersionName] = useState('')
  const [canUndo, setCanUndo] = useState(false)
  const [jdText, setJdText] = useState('')
  const [jdFilename, setJdFilename] = useState('')
  const [experienceText, setExperienceText] = useState('')
  const [experienceFilename, setExperienceFilename] = useState('')
  const [preferences, setPreferences] = useState<Preferences>(DEFAULT_PREFERENCES)
  const [preferenceDraft, setPreferenceDraft] = useState('')
  const [showPreferenceConfirm, setShowPreferenceConfirm] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [showSettings, setShowSettings] = useState(false)
  const [settingsMessage, setSettingsMessage] = useState('')
  const [config, setConfig] = useState<ModelConfig>({ base_url: '', model_name: '', api_key: '' })
  const [templateConfig, setTemplateConfig] = useState<TemplateConfig>({ font_size: 10.5, line_height: 1.55, margin_top: 14, margin_right: 16, margin_bottom: 14, margin_left: 16 })
  const resumeInput = useRef<HTMLInputElement>(null)
  const jdInput = useRef<HTMLInputElement>(null)
  const experienceInput = useRef<HTMLInputElement>(null)
  const workspaceRef = useRef<HTMLElement>(null)

  useEffect(() => {
    const checkHealth = () => fetch(`${API_BASE}/api/health`).then((r) => r.ok ? r.json() : Promise.reject()).then(setHealth).catch(() => setHealth(null))
    checkHealth(); const timer = window.setInterval(checkHealth, 3000); return () => window.clearInterval(timer)
  }, [])
  useEffect(() => {
    fetch(`${API_BASE}/api/resume`).then((r) => r.json()).then((p) => { if (p.exists) { setResume(p); setStructured(p.parsed.structured ?? null); setAssets(p.parsed.assets ?? []); setOriginalFileUrl(`${API_BASE}/api/resume/file?t=${Date.now()}`) } }).catch(() => undefined)
    fetch(`${API_BASE}/api/template`).then((r) => r.json()).then((p) => { if (p.config) setTemplateConfig(p.config) }).catch(() => undefined)
    fetch(`${API_BASE}/api/experiences`).then((r) => r.json()).then((p) => { if (p.exists) { setExperienceText(p.text); setExperienceFilename(p.filename) } }).catch(() => undefined)
    fetch(`${API_BASE}/api/preferences`).then((r) => r.json()).then((p) => { setPreferences(p); setPreferenceDraft(p.profile_text ?? '') }).catch(() => undefined)
    fetch(`${API_BASE}/api/model-config`).then((r) => r.json()).then((p) => setConfig({ base_url: p.base_url ?? '', model_name: p.model_name ?? '', api_key: '' })).catch(() => undefined)
  }, [])
  useEffect(() => {
    if (!dragging) return
    const move = (event: PointerEvent) => { const rect = workspaceRef.current?.getBoundingClientRect(); if (!rect) return; if (dragging === 'vertical') setLeftWidth(Math.min(60, Math.max(25, ((event.clientX - rect.left) / rect.width) * 100))); else { const maxTop = Math.min(82, ((rect.height - 138) / rect.height) * 100); setTopHeight(Math.min(maxTop, Math.max(20, ((event.clientY - rect.top) / rect.height) * 100))) } }
    const stop = () => setDragging(null); window.addEventListener('pointermove', move); window.addEventListener('pointerup', stop); return () => { window.removeEventListener('pointermove', move); window.removeEventListener('pointerup', stop) }
  }, [dragging])

  async function apiJson(url: string, options?: RequestInit) { const response = await fetch(`${API_BASE}${url}`, options); const payload = await response.json(); if (!response.ok) throw new Error(payload.detail ?? '操作失败'); return payload }
  async function uploadResume(file: File) { setBusy(true); setError(''); const form = new FormData(); form.append('file', file); try { const p = await apiJson('/api/import/resume', { method: 'POST', body: form }); setResume(p); setStructured(p.parsed.structured ?? null); setAssets(p.parsed.assets ?? []); setResumeVersionId(''); setOriginalFileUrl(`${API_BASE}/api/resume/file?t=${Date.now()}`); const template = await apiJson('/api/template'); if (template.config) setTemplateConfig(template.config) } catch (e) { setError(e instanceof Error ? e.message : '简历导入失败') } finally { setBusy(false) } }
  async function uploadExperiences(file: File) { setBusy(true); setError(''); const form = new FormData(); form.append('file', file); try { const p = await apiJson('/api/import/experiences', { method: 'POST', body: form }); setExperienceText(p.text ?? ''); setExperienceFilename(file.name) } catch (e) { setError(e instanceof Error ? e.message : '备用经历导入失败') } finally { setBusy(false) } }
  async function saveExperiencesText(text: string) { setExperienceText(text); if (!text.trim()) return; try { await apiJson('/api/import/experiences-text', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text }) }) } catch (e) { setError(e instanceof Error ? e.message : '备用经历保存失败') } }
  async function uploadJd(file: File) { setBusy(true); setError(''); const form = new FormData(); form.append('file', file); try { const p = await apiJson('/api/import/jd', { method: 'POST', body: form }); setJdText(p.text ?? ''); setJdFilename(file.name) } catch (e) { setError(e instanceof Error ? e.message : 'JD 导入失败') } finally { setBusy(false) } }
  async function savePreferences(next: Preferences) { try { const p = await apiJson('/api/preferences', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(next) }); setPreferences(p); setPreferenceDraft(p.profile_text ?? ''); setSettingsMessage('简历修改偏好已保存。') } catch (e) { setError(e instanceof Error ? e.message : '偏好保存失败') } }
  async function finishColdStart() { await savePreferences({ ...preferences, calibrated: true }) }

  async function sendMessage() {
    const value = message.trim(); if (!value || busy) return
    const next = [...chat, { role: 'user' as const, content: value }]; setChat(next); setMessage(''); setBusy(true); setError('')
    try { const p = await apiJson('/api/chat', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ jd_text: jdText, message: value, history: chat, version_id: resumeVersionId }) }); if (p.mode === 'edit' && p.resume_content) { setStructured(p.resume_content); setCanUndo(Boolean(p.can_undo)) } setChat([...next, { role: 'assistant', content: p.content }]) }
    catch (e) { const text = e instanceof Error ? e.message : 'AI 对话失败'; setChat([...next, { role: 'assistant', content: `⚠ ${text}` }]); setError(text) } finally { setBusy(false) }
  }
  async function generateResume() {
    if (!resume || !jdText.trim() || busy) { setError('请先上传简历并输入 JD。'); return }
    if (!preferences.calibrated) { setError('请先确认首次简历修改设置。'); return }
    setBusy(true); setError('')
    try { const p = await apiJson('/api/generate', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ jd_text: jdText, history: chat }) }); setStructured(p.content); setResumeVersionId(p.version_id); setVersionName(p.display_name ?? '当前岗位版本'); setCanUndo(false); const analysis = p.match_analysis ?? {}; const summary = [`实际匹配：${analysis.actual_match || '待结合材料判断'}`, `简历呈现：${analysis.resume_match || '已按JD调整'}`, `主要修改：${analysis.changes || '强化相关经历并压缩弱相关内容'}`, `材料缺口：${analysis.gaps || '未发现明确缺口'}`].join('\n'); const note = p.review_notes?.length ? `\n复核：${p.review_notes.join(' ')}` : ''; setChat((items) => [...items, { role: 'assistant', content: `已生成当前岗位版本。\n${summary}${note}` }]) }
    catch (e) { setError(e instanceof Error ? e.message : '简历生成失败') } finally { setBusy(false) }
  }
  async function saveStructured(next: ResumeStructured) { setStructured(next); if (!resumeVersionId) return; try { const p = await apiJson(`/api/versions/${resumeVersionId}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ content: next }) }); setStructured(p.content); setCanUndo(Boolean(p.can_undo)) } catch (e) { setError(e instanceof Error ? e.message : '修改保存失败') } }
  async function undoVersion() { if (!resumeVersionId) return; try { const p = await apiJson(`/api/versions/${resumeVersionId}/undo`, { method: 'POST' }); setStructured(p.content); setCanUndo(false) } catch (e) { setError(e instanceof Error ? e.message : '撤销失败') } }
  async function exportPdf() {
    if (!resumeVersionId || busy) { setError('请先生成岗位版本。'); return }
    setBusy(true); setError('')
    try { const p = await apiJson(`/api/versions/${resumeVersionId}/export`, { method: 'POST' }); const file = await fetch(`${API_BASE}/api/versions/${resumeVersionId}/pdf`); if (!file.ok) throw new Error('PDF 下载失败'); const url = URL.createObjectURL(await file.blob()); const a = document.createElement('a'); a.href = url; a.download = p.filename ?? `${versionName || 'resume'}.pdf`; a.click(); URL.revokeObjectURL(url); const allowedPages = preferences.page_limit === 'one' ? 1 : preferences.page_limit === 'two' ? 2 : Infinity; if (p.page_count > allowedPages) setChat((items) => [...items, { role: 'assistant', content: `导出的PDF为${p.page_count}页，超过你设置的页数限制，请压缩内容或调整版式。` }]); if (!preferences.profile_text) { try { const suggestion = await apiJson('/api/preferences/suggest', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ version_id: resumeVersionId }) }); setPreferenceDraft(suggestion.suggestion ?? ''); setShowPreferenceConfirm(true) } catch { /* PDF export remains successful */ } } }
    catch (e) { setError(e instanceof Error ? e.message : 'PDF 导出失败') } finally { setBusy(false) }
  }
  async function saveTemplate() { await apiJson('/api/template', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ config: templateConfig }) }); setSettingsMessage('版式设置已保存。') }
  async function saveConfig() { setBusy(true); setError(''); setSettingsMessage(''); try { const p = await apiJson('/api/model-config', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(config) }); setSettingsMessage(p.has_api_key ? '已保存，API Key 已配置。' : '已保存，但尚未填写 API Key。'); setConfig((current) => ({ ...current, api_key: '' })) } catch (e) { const text = e instanceof Error ? e.message : '设置保存失败'; setSettingsMessage(text); setError(text) } finally { setBusy(false) } }
  function startDrag(kind: 'vertical' | 'horizontal', event: ReactPointerEvent) { event.preventDefault(); setDragging(kind) }

  return <main className="shell">
    <header className="topbar"><div><p className="eyebrow">LOCAL RESUME TAILOR</p><h1>简历工作台</h1></div><div className={`status ${health ? 'online' : 'offline'}`}><span /> {health ? '本地服务已连接' : '本地服务未启动'}</div></header>
    <section className="workspace" ref={workspaceRef}><aside className="left-column" style={{ flexBasis: `${leftWidth}%` }}>
      <section className="panel context-panel" style={{ flexBasis: `${topHeight}%` }}><div className="panel-heading"><span>工作区</span><button className="ghost-button" onClick={() => setShowSettings((v) => !v)}>设置</button></div>
        {showSettings && <div className="settings-card"><input placeholder="Base URL" value={config.base_url} onChange={(e) => setConfig({ ...config, base_url: e.target.value })} /><input placeholder="模型名称" value={config.model_name} onChange={(e) => setConfig({ ...config, model_name: e.target.value })} /><input type="password" placeholder="API Key（留空则保留现有设置）" value={config.api_key} onChange={(e) => setConfig({ ...config, api_key: e.target.value })} /><button className="primary-button" onClick={() => void saveConfig()}>保存模型设置</button><label>字号 <input type="number" step="0.5" value={templateConfig.font_size} onChange={(e) => setTemplateConfig({ ...templateConfig, font_size: Number(e.target.value) })} /></label><label>行距 <input type="number" step="0.05" value={templateConfig.line_height} onChange={(e) => setTemplateConfig({ ...templateConfig, line_height: Number(e.target.value) })} /></label><label>上下边距 mm <input type="number" value={templateConfig.margin_top} onChange={(e) => setTemplateConfig({ ...templateConfig, margin_top: Number(e.target.value), margin_bottom: Number(e.target.value) })} /></label><button className="ghost-button" onClick={() => void saveTemplate()}>保存版式设置</button>{preferences.calibrated && <><label>简历修改偏好<textarea value={preferenceDraft} maxLength={500} onChange={(e) => setPreferenceDraft(e.target.value)} /></label><div className="upload-actions"><button className="ghost-button" onClick={() => void savePreferences({ ...preferences, profile_text: preferenceDraft })}>保存偏好</button><button className="ghost-button" onClick={() => void savePreferences({ ...preferences, profile_text: '', calibrated: false })}>重新校准</button></div></>}{settingsMessage && <span className="settings-message">{settingsMessage}</span>}</div>}
        <input ref={resumeInput} hidden type="file" accept=".pdf,.docx" onChange={(e) => { const f = e.target.files?.[0]; if (f) void uploadResume(f) }} /><input ref={jdInput} hidden type="file" accept=".pdf,.docx" onChange={(e) => { const f = e.target.files?.[0]; if (f) void uploadJd(f) }} /><input ref={experienceInput} hidden type="file" accept=".pdf,.docx,.txt,.md" onChange={(e) => { const f = e.target.files?.[0]; if (f) void uploadExperiences(f) }} />
        <div className="empty-card">{resume ? <><strong>{resume.filename}</strong><p>已读取 {resume.parsed.text.length} 个字符。{resume.parsed.warnings?.[0] ?? ''}</p></> : <><strong>先上传你的主简历</strong><p>支持 DOCX / PDF。</p></>}<div className="upload-actions"><button className="primary-button" onClick={() => resumeInput.current?.click()} disabled={busy}>{resume ? '替换简历' : '上传简历'}</button><button className="ghost-button" onClick={() => jdInput.current?.click()} disabled={busy}>上传 JD</button></div>{jdText && <p className="loaded-jd">JD：{jdFilename || '已粘贴'} · {jdText.length} 字</p>}</div>
        {resume && !preferences.calibrated && <div className="cold-start"><strong>首次简历修改设置</strong>
          <label><span>页数<small>最终PDF的硬性上限</small></span><select value={preferences.page_limit} onChange={(e) => setPreferences({ ...preferences, page_limit: e.target.value as Preferences['page_limit'] })}><option value="one">必须一页</option><option value="two">最多两页</option><option value="unlimited">不限制页数</option></select></label>
          <label><span>结构<small>AI可否移动、增删板块</small></span><select value={preferences.structure_mode} onChange={(e) => setPreferences({ ...preferences, structure_mode: e.target.value as Preferences['structure_mode'] })}><option value="preserve">保持板块及顺序</option><option value="reorder">只允许移动，不增删</option><option value="rebuild">允许增删、合并和移动</option></select></label>
          <label><span>版式<small>字体、边距和照片位置</small></span><select value={preferences.layout_mode} onChange={(e) => setPreferences({ ...preferences, layout_mode: e.target.value as Preferences['layout_mode'] })}><option value="preserve">严格继承原简历</option><option value="adaptive">仅为满足页数自动微调</option></select></label>
          <label><span>时间<small>同一板块内的经历顺序</small></span><select value={preferences.date_order} onChange={(e) => setPreferences({ ...preferences, date_order: e.target.value as Preferences['date_order'] })}><option value="desc">最近经历优先（推荐）</option><option value="asc">最早经历优先</option><option value="relevance">允许按岗位相关度排序</option></select></label>
          <button className="primary-button" onClick={() => void finishColdStart()}>确认并开始</button></div>}
        <div className="jd-input-card"><label htmlFor="jd-text">粘贴 JD</label><textarea id="jd-text" value={jdText} onChange={(e) => { setJdText(e.target.value); setJdFilename('') }} placeholder="把岗位描述粘贴到这里……" /></div><div className="jd-input-card"><label htmlFor="experience-text">备用经历库（可选）</label><textarea id="experience-text" value={experienceText} onChange={(e) => setExperienceText(e.target.value)} onBlur={(e) => void saveExperiencesText(e.target.value)} placeholder="粘贴补充经历……" /><button className="ghost-button" onClick={() => experienceInput.current?.click()} disabled={busy}>{experienceFilename ? `替换：${experienceFilename}` : '上传备用经历库'}</button></div>{error && <p className="error-message">{error}</p>}
      </section><div className="splitter horizontal" onPointerDown={(event) => startDrag('horizontal', event)} />
      <section className="panel chat-panel"><div className="panel-heading"><span>AI 协作</span><span className="muted">{chat.length} 条消息</span></div><div className="chat-body">{resume && <div className="system-note">已载入主简历：{resume.filename}</div>}{jdText && <div className="system-note">已载入 JD：{jdText.length} 字</div>}{chat.length === 0 ? <p className="chat-placeholder">可直接生成，也可以先告诉 AI 你的要求。</p> : chat.map((item, i) => <div className={item.role === 'user' ? 'user-message' : 'assistant-message'} key={`${item.role}-${i}`} style={{ whiteSpace: 'pre-wrap' }}>{renderPlain(item.content)}</div>)}</div><div className="composer"><textarea value={message} onChange={(e) => setMessage(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); void sendMessage() } }} placeholder={resumeVersionId ? '继续告诉 AI 如何修改当前版本……' : '告诉 AI 你的要求……'} /><button className="send-button" onClick={() => void sendMessage()} disabled={busy}>发送</button></div></section>
    </aside><div className="splitter vertical" onPointerDown={(event) => startDrag('vertical', event)} /><section className="preview-panel"><div className="panel-heading preview-heading"><span>{resumeVersionId ? versionName || '当前岗位版本' : '原始简历预览'}</span><div className="preview-actions">{canUndo && <button className="ghost-button" onClick={() => void undoVersion()}>撤销</button>}<button className="ghost-button" onClick={() => void generateResume()} disabled={busy}>生成简历</button><button className="primary-button" onClick={() => void exportPdf()} disabled={busy}>导出 PDF</button></div></div><div className="resume-placeholder">{!resumeVersionId && resume?.format === 'pdf' && originalFileUrl ? <iframe className="original-pdf" src={originalFileUrl} title="原始简历 PDF" /> : <ResumePaper structured={structured} assets={assets} template={templateConfig} editable={Boolean(resumeVersionId)} onChange={(next) => void saveStructured(next)} />}</div></section></section>
    {showPreferenceConfirm && <div className="modal-backdrop"><div className="preference-modal"><h2>确认简历修改偏好</h2><p>这是根据第一次真实修改总结的长期偏好，不包含当前岗位的一次性决定。</p><textarea value={preferenceDraft} maxLength={500} onChange={(e) => setPreferenceDraft(e.target.value)} /><div className="preview-actions"><button className="ghost-button" onClick={() => setShowPreferenceConfirm(false)}>暂不保存</button><button className="primary-button" onClick={() => { void savePreferences({ ...preferences, profile_text: preferenceDraft }); setShowPreferenceConfirm(false) }}>确认并冻结</button></div></div></div>}
  </main>
}
