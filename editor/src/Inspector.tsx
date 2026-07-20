import { useEffect, useState } from 'react'
import { api } from './api'
import type { GraphNode, HandleSide, StepType } from './types'

type Props = {
  node?: GraphNode
  stepType?: StepType
  readOnly: boolean
  onChange: (data: GraphNode['data']) => void
  picker?: { workflowId: number; clientId: string; agentConnected: boolean; event?: PickerEvent; drafts?: Record<string, PickerDraft>; onDraftChange?: (key: string, draft: PickerDraft) => void }
}

type PickerEvent = { type: string; session_id?: string; payload?: Record<string, unknown> }
type LocatorResult = { locator: LocatorValue; fallback_locators?: LocatorValue[]; element?: { tag_name?: string; text?: string | null; role?: string | null }; validation?: { match_count?: number; matches_selected_element?: boolean } }
export type PickerDraft = { sessionId?: string; status?: string; requestedUrl: string; pairingCode: string; result?: LocatorResult }

function describeLocator(locator: LocatorValue): string {
  const strategy = String(locator.strategy ?? 'locator')
  if (strategy === 'role') return `Role ${String(locator.role ?? 'element')}${locator.name ? ` named “${String(locator.name)}”` : ''}`
  if (strategy === 'label') return `Label “${String(locator.label ?? '')}”`
  if (strategy === 'text') return `Visible text “${String(locator.text ?? '')}”`
  if (strategy === 'css') return `CSS selector ${String(locator.selector ?? '')}`
  return strategy
}

type LocatorValue = Record<string, unknown>
const RUN_INPUT_TEMPLATE = /^\{\{\s*inputs\.([a-zA-Z0-9_.]+)\s*\}\}$/
const LOCATOR_STRATEGIES = ['label', 'role', 'text', 'css'] as const
type LocatorStrategy = typeof LOCATOR_STRATEGIES[number]

const HANDLE_OPTIONS: Array<{ value?: HandleSide; label: string }> = [
  { label: 'Auto' },
  { value: 'top', label: 'Top' },
  { value: 'right', label: 'Right' },
  { value: 'bottom', label: 'Bottom' },
  { value: 'left', label: 'Left' },
]

const Help = ({ text }: { text: string }) => (
  <span className="field-help" title={text} aria-label={text}>?</span>
)

function getSchemaProperty(stepType: StepType | undefined, path: string): Record<string, unknown> | undefined {
  const properties = stepType?.args_schema && typeof stepType.args_schema === 'object'
    ? (stepType.args_schema as Record<string, unknown>).properties
    : undefined
  if (!properties || typeof properties !== 'object') return undefined
  const property = (properties as Record<string, unknown>)[path]
  return property && typeof property === 'object' && !Array.isArray(property) ? property as Record<string, unknown> : undefined
}

function isNumericField(stepType: StepType | undefined, path: string, value: unknown): boolean {
  const property = getSchemaProperty(stepType, path)
  const schemaType = property?.type
  if (schemaType === 'integer' || schemaType === 'number') return true
  if (Array.isArray(schemaType) && schemaType.some((item) => item === 'integer' || item === 'number')) return true
  return typeof value === 'number'
}

function isSecondsTimeoutField(path: string): boolean {
  return path === 'timeout_ms'
}

function getRunInputKey(value: unknown): string | undefined {
  return typeof value === 'string' ? RUN_INPUT_TEMPLATE.exec(value)?.[1] : undefined
}

function supportsRunInput(stepType: StepType | undefined, path: string, widget: string, value: unknown): boolean {
  if (widget === 'locator' || widget === 'select-option' || widget === 'ticket-fields' || widget === 'select') return false
  const type = getSchemaProperty(stepType, path)?.type
  if (typeof type === 'string') return ['string', 'integer', 'number', 'boolean'].includes(type)
  if (Array.isArray(type)) return type.some((item) => ['string', 'integer', 'number', 'boolean'].includes(String(item)))
  return ['string', 'number', 'boolean'].includes(typeof value)
}

function getFieldLabel(path: string): string {
  if (path === 'state') return 'Wait until'
  return isSecondsTimeoutField(path) ? 'Seconds' : path
}

function toDisplayNumber(path: string, value: unknown): string {
  if (value === undefined || value === null || value === '') return ''
  if (typeof value !== 'number' || Number.isNaN(value)) return String(value)
  return isSecondsTimeoutField(path) ? String(value / 1000) : String(value)
}

function fromDisplayNumber(path: string, value: string): number | undefined {
  if (value.trim() === '') return undefined
  const parsed = Number(value)
  if (Number.isNaN(parsed)) return undefined
  return isSecondsTimeoutField(path) ? Math.round(parsed * 1000) : parsed
}

function getTextCandidate(value: LocatorValue, keys: string[]): string {
  for (const key of keys) {
    const candidate = value[key]
    if (typeof candidate === 'string' && candidate.trim()) return candidate
  }
  return ''
}

function normalizeLocatorTarget(value: LocatorValue, strategy: LocatorStrategy): LocatorValue {
  const base = { strategy, exact: value.exact !== false }
  if (strategy === 'label') return { ...base, label: getTextCandidate(value, ['label', 'name', 'text']) }
  if (strategy === 'role') return { ...base, role: getTextCandidate(value, ['role']) || 'button', name: getTextCandidate(value, ['name', 'label', 'text']) }
  if (strategy === 'text') return { ...base, text: getTextCandidate(value, ['text', 'name', 'label']) }
  return { ...base, selector: getTextCandidate(value, ['selector']) }
}

function ConnectionSideFields({ node, readOnly, onChange }: { node: GraphNode; readOnly: boolean; onChange: (data: GraphNode['data']) => void }) {
  if (node.data.kind === 'comment') return null

  const setSide = (key: 'source_handle' | 'target_handle', side: string) => {
    onChange({
      ...node.data,
      [key]: side === '' ? undefined : side,
    })
  }

  return (
    <fieldset className="connection-side-editor">
      <legend>Connection sides</legend>
      <label>
        Outgoing side
        <Help text="Auto chooses a side based on the connected nodes. Manual overrides keep the chosen side." />
        <select
          disabled={readOnly}
          value={node.data.source_handle ?? ''}
          onChange={(e) => setSide('source_handle', e.target.value)}
        >
          {HANDLE_OPTIONS.map((option) => <option key={option.label} value={option.value ?? ''}>{option.label}</option>)}
        </select>
      </label>
      {node.data.kind !== 'start' && (
        <label>
          Incoming side
          <Help text="Auto chooses the side from the position of the upstream node." />
          <select
            disabled={readOnly}
            value={node.data.target_handle ?? ''}
            onChange={(e) => setSide('target_handle', e.target.value)}
          >
            {HANDLE_OPTIONS.map((option) => <option key={option.label} value={option.value ?? ''}>{option.label}</option>)}
          </select>
        </label>
      )}
    </fieldset>
  )
}

function LocatorTargetFields({ prefix = '', value, disabled, onChange }: { prefix?: string; value: LocatorValue; disabled: boolean; onChange: (value: LocatorValue) => void }) {
  const strategy = LOCATOR_STRATEGIES.includes(value.strategy as LocatorStrategy) ? value.strategy as LocatorStrategy : 'label'
  return (
    <div className="locator-target-fields">
      <label>
        {prefix}Strategy <Help text="How Playwright locates the element. Prefer Label or Role; use CSS only when accessible locators are unavailable." />
        <select disabled={disabled} value={strategy} onChange={(e) => onChange(normalizeLocatorTarget(value, e.target.value as LocatorStrategy))}>
          <option value="label">Label</option>
          <option value="role">Role</option>
          <option value="text">Visible text</option>
          <option value="css">CSS selector</option>
        </select>
      </label>
      {strategy === 'label' && <label>{prefix}Label <Help text="The visible label associated with a form control." /><input disabled={disabled} value={String(value.label ?? '')} placeholder="Email address" onChange={(e) => onChange({ ...value, label: e.target.value })} /></label>}
      {strategy === 'role' && <><label>{prefix}Role <Help text="The accessible role, such as button or textbox." /><input disabled={disabled} value={String(value.role ?? '')} placeholder="button" onChange={(e) => onChange({ ...value, role: e.target.value })} /></label><label>{prefix}Accessible name <Help text="The element's accessible name." /><input disabled={disabled} value={String(value.name ?? '')} placeholder="Submit" onChange={(e) => onChange({ ...value, name: e.target.value })} /></label></>}
      {strategy === 'text' && <label>{prefix}Visible text <Help text="Text visibly rendered inside the target element." /><input disabled={disabled} value={String(value.text ?? '')} placeholder="Success" onChange={(e) => onChange({ ...value, text: e.target.value })} /></label>}
      {strategy === 'css' && <label>{prefix}CSS selector <Help text="A CSS selector only; XPath and JavaScript are rejected." /><input disabled={disabled} value={String(value.selector ?? '')} placeholder="#username" onChange={(e) => onChange({ ...value, selector: e.target.value })} /></label>}
      <label className="inline-field"><input disabled={disabled} type="checkbox" checked={value.exact !== false} onChange={(e) => onChange({ ...value, exact: e.target.checked })} /> Exact match <Help text="When enabled, the label, name, or text must match exactly." /></label>
    </div>
  )
}

function LocatorEditor({ value, disabled, onChange }: { value: unknown; disabled: boolean; onChange: (value: LocatorValue) => void }) {
  const locator = value && typeof value === 'object' && !Array.isArray(value) ? value as LocatorValue : { strategy: 'label', label: '', exact: true }
  const match = String(locator.match ?? 'strict')
  const scope = locator.scope && typeof locator.scope === 'object' ? locator.scope as LocatorValue : undefined

  return (
    <div className="locator-editor">
      <LocatorTargetFields
        value={locator}
        disabled={disabled}
        onChange={(target) => onChange({ ...target, match: locator.match ?? 'strict', ...(locator.nth === undefined ? {} : { nth: locator.nth }), ...(scope ? { scope } : {}) })}
      />
      <label>
        Match mode <Help text="Strict requires exactly one match." />
        <select
          disabled={disabled}
          value={match}
          onChange={(e) => onChange({ ...locator, match: e.target.value, ...(e.target.value === 'nth' ? { nth: Number(locator.nth ?? 0) } : { nth: undefined }) })}
        >
          <option value="strict">Strict (unique)</option>
          <option value="first">First</option>
          <option value="last">Last</option>
          <option value="nth">Nth</option>
        </select>
      </label>
      {match === 'nth' && <label>Nth index <Help text="Zero-based index: 0 is the first matching element." /><input disabled={disabled} type="number" min="0" max="99" value={Number(locator.nth ?? 0)} onChange={(e) => onChange({ ...locator, nth: Number(e.target.value) })} /></label>}
      <label className="inline-field"><input disabled={disabled} type="checkbox" checked={Boolean(scope)} onChange={(e) => onChange(e.target.checked ? { ...locator, scope: { strategy: 'css', selector: '.container', exact: true } } : { ...locator, scope: undefined })} /> Limit to a scope <Help text="Find a container first, then search inside that container." /></label>
      {scope && <fieldset><legend>Scope locator</legend><LocatorTargetFields prefix="Scope " value={scope} disabled={disabled} onChange={(next) => onChange({ ...locator, scope: next })} /></fieldset>}
    </div>
  )
}

function PickerControls({ workflowId, nodeId, field, disabled, clientId, agentConnected, event, onAccept, draft, onDraftChange }: { workflowId: number; nodeId: string; field: string; disabled: boolean; clientId: string; agentConnected: boolean; event?: PickerEvent; onAccept: (locator: LocatorValue) => void; draft?: PickerDraft; onDraftChange: (next: PickerDraft) => void }) {
  const [localDraft, setLocalDraft] = useState<PickerDraft>({ requestedUrl: '', pairingCode: '' })
  const currentDraft = draft ?? localDraft
  const sessionId = currentDraft.sessionId
  const status = currentDraft.status ?? (agentConnected ? 'Browser ready' : 'Agent unavailable')
  const requestedUrl = currentDraft.requestedUrl
  const pairingCode = currentDraft.pairingCode
  const result = currentDraft.result
  const update = (changes: Partial<PickerDraft>) => {
    const next = { ...currentDraft, ...changes }
    if (draft === undefined) setLocalDraft(next)
    onDraftChange(next)
  }

  useEffect(() => { if (!sessionId) update({ status: agentConnected ? 'Browser ready' : 'Agent unavailable' }) }, [agentConnected, sessionId])
  useEffect(() => {
    if (!event || event.session_id !== sessionId) return
    if (event.type === 'picker.session.updated') update({ status: String(event.payload?.status ?? 'Waiting for agent') })
    if (event.type === 'picker.session.accepted') update({ status: 'Opening browser' })
    if (event.type === 'browser.opened') update({ status: 'Browser ready' })
    if (event.type === 'picker.inspect.started') update({ status: 'Select an element' })
    if (event.type === 'picker.inspect.cancelled') update({ status: 'Browser ready' })
    if (event.type === 'picker.element.selected') update({ result: event.payload as LocatorResult, status: 'Element selected' })
    if (event.type === 'picker.error') update({ status: String(event.payload?.message ?? 'Picker failed') })
  }, [event, sessionId])

  const start = async () => {
    try {
      update({ status: 'Waiting for agent' })
      const created = await api<{ session_id: string; status: string }>('/editor-picker/sessions', { method: 'POST', body: JSON.stringify({ workflow_id: workflowId, node_id: nodeId, client_id: clientId, ...(requestedUrl.trim() ? { requested_url: requestedUrl.trim() } : {}) }) })
      update({ sessionId: created.session_id, status: created.status === 'waiting_for_agent' ? 'Waiting for agent' : 'Opening browser', result: undefined })
    } catch (error) { update({ status: (error as Error).message }) }
  }
  const pair = async () => {
    try {
      await api('/editor-picker/pairings/approve', { method: 'POST', body: JSON.stringify({ code: pairingCode.trim().toUpperCase() }) })
      update({ status: 'Pairing approved; waiting for agent', pairingCode: '' })
    } catch (error) { update({ status: (error as Error).message }) }
  }
  const inspect = async () => { if (!sessionId) return; try { await api(`/editor-picker/sessions/${sessionId}/inspect`, { method: 'POST' }); update({ status: 'Starting selection' }) } catch (error) { update({ status: (error as Error).message }) } }
  const stopInspection = async () => { if (!sessionId) return; try { await api(`/editor-picker/sessions/${sessionId}/inspect/cancel`, { method: 'POST' }); update({ result: undefined, status: 'Browser ready' }) } catch (error) { update({ status: (error as Error).message }) } }
  const cancel = async () => {
    if (!sessionId) return
    try {
      const startup = ['Waiting for agent', 'Opening browser', 'created', 'waiting_for_agent', 'agent_connected', 'browser_starting'].includes(status)
      const inspecting = status === 'Select an element'
      if (startup || !inspecting) {
        await api(`/editor-picker/sessions/${sessionId}/cancel`, { method: 'POST' })
        update({ sessionId: undefined, result: undefined, status: 'Picker cancelled' })
      } else await stopInspection()
    } catch (error) { update({ status: (error as Error).message }) }
  }

  return <section className="picker-controls" aria-label={`Element picker for ${field}`}>
    <h3>Local element picker</h3><p className={agentConnected ? 'valid' : 'error'}>{status}</p>
    {!sessionId && <>{!agentConnected && <div className="picker-pairing"><label>Agent pairing code<input disabled={disabled} value={pairingCode} placeholder="AB12-CD34" onChange={(e) => update({ pairingCode: e.target.value.toUpperCase().replace(/[^A-Z0-9-]/g, '') })} /></label><button type="button" disabled={disabled || pairingCode.length < 6} onClick={pair}>Pair agent</button></div>}<label>Optional start URL<input disabled={disabled || !agentConnected} value={requestedUrl} placeholder="https://example.com" onChange={(e) => update({ requestedUrl: e.target.value })} /></label><button type="button" disabled={disabled || !agentConnected} onClick={start}>Pick Element</button></>}
    {sessionId && !result && <><button type="button" disabled={disabled || status !== 'Browser ready'} onClick={inspect}>Start Selecting</button><button type="button" onClick={cancel}>{status === 'Select an element' ? 'Cancel inspection' : 'Close picker'}</button></>}
    {result && <div className="picker-preview">
      <h4>Selected element</h4>
      <p className="picker-element-summary"><code>&lt;{result.element?.tag_name ?? 'element'}&gt;</code>{result.element?.role ? ` · ${result.element.role}` : ''}{result.element?.text ? ` · “${result.element.text}”` : ''}</p>
      <h4>Preferred locator</h4>
      <p className="picker-locator-summary"><strong>{describeLocator(result.locator)}</strong></p>
      <p className={result.validation?.matches_selected_element ? 'valid' : 'error'}>{result.validation?.matches_selected_element ? `Validated · ${result.validation?.match_count ?? '?'} match` : 'Could not validate this locator'}</p>
      <details><summary>Technical locator details</summary><pre>{JSON.stringify(result.locator, null, 2)}</pre></details>
      {!!result.fallback_locators?.length && <details><summary>{result.fallback_locators.length} fallback locator{result.fallback_locators.length === 1 ? '' : 's'}</summary><ul>{result.fallback_locators.map((locator, index) => <li key={index}>{describeLocator(locator)}<details><summary>Details</summary><pre>{JSON.stringify(locator, null, 2)}</pre></details></li>)}</ul></details>}
      <div className="picker-actions"><button type="button" disabled={disabled || !result.validation?.matches_selected_element} onClick={async () => { try { await api(`/editor-picker/sessions/${sessionId}/complete`, { method: 'POST' }); onAccept(result.locator); update({ status: 'Locator accepted locally; save the draft when ready', sessionId: undefined }) } catch (error) { update({ status: (error as Error).message }) } }}>Accept locator</button><button type="button" onClick={() => { void stopInspection() }}>Pick Again</button></div>
    </div>}
  </section>
}

function SelectOptionEditor({ value, disabled, onChange }: { value: unknown; disabled: boolean; onChange: (value: unknown) => void }) {
  const option = value && typeof value === 'object' ? value as Record<string, unknown> : { by: 'label', value: '' }
  const by = String(option.by ?? 'label')

  return (
    <div className="select-option-editor">
      <label>
        Choose option by <Help text="Select by visible label, submitted value, or zero-based index." />
        <select disabled={disabled} value={by} onChange={(e) => onChange({ by: e.target.value, value: e.target.value === 'index' ? 0 : '' })}>
          <option value="label">Visible label</option>
          <option value="value">HTML value</option>
          <option value="index">Index</option>
        </select>
      </label>
      <label>
        Option {by}
        <Help text={by === 'index' ? 'Zero-based option index.' : `Exact ${by} passed to Playwright.`} />
        <input disabled={disabled} type={by === 'index' ? 'number' : 'text'} min={by === 'index' ? 0 : undefined} value={String(option.value ?? '')} onChange={(e) => onChange({ ...option, value: by === 'index' ? Number(e.target.value) : e.target.value })} />
      </label>
    </div>
  )
}

function TicketFields({ value, disabled, onChange }: { value: unknown; disabled: boolean; onChange: (value: unknown) => void }) {
  const rows = Array.isArray(value) ? value as Array<Record<string, unknown>> : []
  const update = (index: number, patch: Record<string, unknown>) => onChange(rows.map((row, i) => i === index ? { ...row, ...patch } : row))

  return (
    <div className="ticket-fields">
      {rows.map((row, index) => (
        <div className="ticket-row" key={index}>
          <strong>Field {index + 1} target</strong>
          <LocatorEditor disabled={disabled} value={row.target} onChange={(target) => update(index, { target })} />
          <select disabled={disabled} aria-label={`Field ${index + 1} control`} value={String(row.control_type ?? 'text')} onChange={(e) => update(index, { control_type: e.target.value, ...(e.target.value === 'select' ? { option: { by: 'label', value: '' } } : { option: undefined }) })}>
            <option>text</option>
            <option>textarea</option>
            <option>select</option>
          </select>
          {row.control_type === 'select' ? <><select disabled={disabled} value={String((row.option as Record<string, unknown>)?.by ?? 'label')} onChange={(e) => update(index, { option: { ...(row.option as object), by: e.target.value } })}><option>label</option><option>value</option><option>index</option></select><input disabled={disabled} value={String((row.option as Record<string, unknown>)?.value ?? '')} onChange={(e) => update(index, { option: { ...(row.option as object), value: (row.option as Record<string, unknown>)?.by === 'index' ? Number(e.target.value) : e.target.value } })} /></> : <input disabled={disabled} placeholder="Value" value={String(row.value ?? '')} onChange={(e) => update(index, { value: e.target.value })} />}
          <button disabled={disabled} onClick={() => onChange(rows.filter((_, i) => i !== index))}>Remove</button>
        </div>
      ))}
      <button disabled={disabled} onClick={() => onChange([...rows, { target: { strategy: 'label', label: 'Field label', exact: true }, control_type: 'text', value: '' }])}>Add field</button>
    </div>
  )
}

export function Inspector({ node, stepType, readOnly, onChange, picker }: Props) {
  const [advanced, setAdvanced] = useState('')
  const [jsonError, setJsonError] = useState('')

  useEffect(() => {
    setAdvanced(JSON.stringify(node?.data.args ?? {}, null, 2))
    setJsonError('')
  }, [node?.id, node?.data.args])

  if (!node) return <aside className="inspector"><h2>Inspector</h2><p>Select a node.</p></aside>
  if (node.data.kind === 'start') return <aside className="inspector"><h2>Start</h2><p>The required entry point cannot be deleted.</p><ConnectionSideFields node={node} readOnly={readOnly} onChange={onChange} /></aside>
  if (node.data.kind === 'comment') return <aside className="inspector"><h2>Comment</h2><textarea disabled={readOnly} value={node.data.text ?? ''} onChange={(e) => onChange({ ...node.data, text: e.target.value })} /></aside>

  if (node.data.kind === 'if' || node.data.kind === 'loop') {
    const args = node.data.args ?? {}
    const setArg = (key: string, value: unknown) => onChange({ ...node.data, args: { ...args, [key]: value } })
    return <aside className="inspector"><h2>{node.data.kind === 'if' ? 'If' : 'Loop'}</h2><p>Read a runtime state value and choose the matching exit.</p><label>State key<input disabled={readOnly} value={String(args.state_key ?? '')} onChange={(e) => setArg('state_key', e.target.value)} /></label><label>Operator<select disabled={readOnly} value={String(args.operator ?? 'equals')} onChange={(e) => setArg('operator', e.target.value)}><option value="equals">Equals</option><option value="not_equals">Does not equal</option><option value="contains">Contains</option><option value="truthy">Is truthy</option><option value="falsy">Is falsy</option></select></label>{!['truthy', 'falsy'].includes(String(args.operator)) && <label>Value<input disabled={readOnly} value={String(args.value ?? '')} onChange={(e) => setArg('value', e.target.value)} /></label>}{node.data.kind === 'loop' && <label>Maximum iterations<input disabled={readOnly} type="number" min="1" max="1000" value={Number(args.max_iterations ?? 10)} onChange={(e) => setArg('max_iterations', Number(e.target.value))} /></label>}<ConnectionSideFields node={node} readOnly={readOnly} onChange={onChange} /></aside>
  }

  const args = node.data.args ?? {}
  const fields = stepType?.editor_schema.fields ?? []
  const changeArg = (key: string, value: unknown) => onChange({ ...node.data, args: { ...args, [key]: value } })

  return (
    <aside className="inspector">
      <h2>{stepType?.name ?? node.data.step_type}</h2>
      <p>{stepType?.description}</p>
      <ConnectionSideFields node={node} readOnly={readOnly} onChange={onChange} />
      {fields.map((field) => (
        <div className="argument-field" key={field.path}><label>
          {getFieldLabel(field.path)}
          {getRunInputKey(args[field.path]) ? <input disabled value={`Resolved from run input: ${getRunInputKey(args[field.path])}`} /> : field.widget === 'ticket-fields' ? <TicketFields disabled={readOnly} value={args[field.path]} onChange={(value) => changeArg(field.path, value)} /> : field.widget === 'locator' ? <LocatorEditor disabled={readOnly} value={args[field.path]} onChange={(value) => changeArg(field.path, value)} /> : field.widget === 'select' ? <select disabled={readOnly} value={String(args[field.path] ?? field.options?.[0]?.value ?? '')} onChange={(e) => changeArg(field.path, e.target.value)}>{(field.options ?? []).map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select> : field.widget === 'select-option' ? <SelectOptionEditor disabled={readOnly} value={args[field.path]} onChange={(value) => changeArg(field.path, value)} /> : typeof args[field.path] === 'boolean' ? <input disabled={readOnly} type="checkbox" checked={Boolean(args[field.path])} onChange={(e) => changeArg(field.path, e.target.checked)} /> : isNumericField(stepType, field.path, args[field.path]) ? <input disabled={readOnly} type="number" step={isSecondsTimeoutField(field.path) ? 0.1 : getSchemaProperty(stepType, field.path)?.type === 'integer' ? 1 : 'any'} value={toDisplayNumber(field.path, args[field.path])} onChange={(e) => changeArg(field.path, fromDisplayNumber(field.path, e.target.value))} /> : <input disabled={readOnly} value={String(args[field.path] ?? '')} onChange={(e) => changeArg(field.path, e.target.value)} />}
          {isSecondsTimeoutField(field.path) && <small className="field-hint">Displayed in seconds, stored as milliseconds.</small>}
        </label>{supportsRunInput(stepType, field.path, field.widget, args[field.path]) && <div className="run-input-control"><label className="inline-field"><input disabled={readOnly} type="checkbox" checked={Boolean(getRunInputKey(args[field.path]))} onChange={(event) => changeArg(field.path, event.target.checked ? `{{ inputs.${field.path} }}` : structuredClone(stepType?.default_args[field.path] ?? ''))} /> Use run input</label>{getRunInputKey(args[field.path]) && <label>Input name<input disabled={readOnly} value={getRunInputKey(args[field.path])} onChange={(event) => { const key = event.target.value.replace(/[^a-zA-Z0-9_.]/g, ''); changeArg(field.path, `{{ inputs.${key || field.path} }}`) }} /></label>}</div>}</div>
      ))}
      {picker && fields.filter((field) => field.widget === 'locator').map((field) => { const draftKey = `${node.id}:${field.path}`; return <PickerControls key={`picker-${field.path}`} workflowId={picker.workflowId} nodeId={node.id} field={field.path} disabled={readOnly} clientId={picker.clientId} agentConnected={picker.agentConnected} event={picker.event} draft={picker.drafts?.[draftKey]} onDraftChange={(draft) => picker.onDraftChange?.(draftKey, draft)} onAccept={(locator) => changeArg(field.path, locator)} /> })}
      <details>
        <summary>Advanced arguments JSON</summary>
        <textarea aria-label="Advanced arguments JSON" disabled={readOnly} value={advanced} onChange={(e) => setAdvanced(e.target.value)} />
        <button disabled={readOnly} onClick={() => {
          try {
            const parsed = JSON.parse(advanced)
            if (!parsed || Array.isArray(parsed) || typeof parsed !== 'object') throw new Error('Arguments must be an object')
            setJsonError('')
            onChange({ ...node.data, args: parsed })
          } catch (error) {
            setJsonError((error as Error).message)
          }
        }}>Apply JSON</button>
        {jsonError && <span className="error">{jsonError}</span>}
      </details>
    </aside>
  )
}
