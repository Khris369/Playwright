import { useEffect, useState } from 'react'
import type { GraphNode, HandleSide, StepType } from './types'

type Props = {
  node?: GraphNode
  stepType?: StepType
  readOnly: boolean
  onChange: (data: GraphNode['data']) => void
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
  if (widget === 'locator' || widget === 'select-option' || widget === 'ticket-fields') return false
  const type = getSchemaProperty(stepType, path)?.type
  if (typeof type === 'string') return ['string', 'integer', 'number', 'boolean'].includes(type)
  if (Array.isArray(type)) return type.some((item) => ['string', 'integer', 'number', 'boolean'].includes(String(item)))
  return ['string', 'number', 'boolean'].includes(typeof value)
}

function getFieldLabel(path: string): string {
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

export function Inspector({ node, stepType, readOnly, onChange }: Props) {
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
          {getRunInputKey(args[field.path]) ? <input disabled value={`Resolved from run input: ${getRunInputKey(args[field.path])}`} /> : field.widget === 'ticket-fields' ? <TicketFields disabled={readOnly} value={args[field.path]} onChange={(value) => changeArg(field.path, value)} /> : field.widget === 'locator' ? <LocatorEditor disabled={readOnly} value={args[field.path]} onChange={(value) => changeArg(field.path, value)} /> : field.widget === 'select-option' ? <SelectOptionEditor disabled={readOnly} value={args[field.path]} onChange={(value) => changeArg(field.path, value)} /> : typeof args[field.path] === 'boolean' ? <input disabled={readOnly} type="checkbox" checked={Boolean(args[field.path])} onChange={(e) => changeArg(field.path, e.target.checked)} /> : isNumericField(stepType, field.path, args[field.path]) ? <input disabled={readOnly} type="number" step={isSecondsTimeoutField(field.path) ? 0.1 : getSchemaProperty(stepType, field.path)?.type === 'integer' ? 1 : 'any'} value={toDisplayNumber(field.path, args[field.path])} onChange={(e) => changeArg(field.path, fromDisplayNumber(field.path, e.target.value))} /> : <input disabled={readOnly} value={String(args[field.path] ?? '')} onChange={(e) => changeArg(field.path, e.target.value)} />}
          {isSecondsTimeoutField(field.path) && <small className="field-hint">Displayed in seconds, stored as milliseconds.</small>}
        </label>{supportsRunInput(stepType, field.path, field.widget, args[field.path]) && <div className="run-input-control"><label className="inline-field"><input disabled={readOnly} type="checkbox" checked={Boolean(getRunInputKey(args[field.path]))} onChange={(event) => changeArg(field.path, event.target.checked ? `{{ inputs.${field.path} }}` : structuredClone(stepType?.default_args[field.path] ?? ''))} /> Use run input</label>{getRunInputKey(args[field.path]) && <label>Input name<input disabled={readOnly} value={getRunInputKey(args[field.path])} onChange={(event) => { const key = event.target.value.replace(/[^a-zA-Z0-9_.]/g, ''); changeArg(field.path, `{{ inputs.${key || field.path} }}`) }} /></label>}</div>}</div>
      ))}
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
