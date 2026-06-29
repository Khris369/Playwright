import { useEffect, useState } from 'react'
import type { GraphNode, StepType } from './types'

type Props = { node?: GraphNode; stepType?: StepType; readOnly: boolean; onChange: (data: GraphNode['data']) => void }

type LocatorValue = Record<string, unknown>

const Help = ({ text }: { text: string }) => <span className="field-help" title={text} aria-label={text}>?</span>

function getSchemaProperty(stepType: StepType | undefined, path: string): Record<string, unknown> | undefined {
  const properties = stepType?.args_schema && typeof stepType.args_schema === 'object'
    ? (stepType.args_schema as Record<string, unknown>).properties
    : undefined
  if (!properties || typeof properties !== 'object') return undefined
  const property = (properties as Record<string, unknown>)[path]
  return property && typeof property === 'object' && !Array.isArray(property)
    ? property as Record<string, unknown>
    : undefined
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

function fieldLabel(path: string): string {
  return isSecondsTimeoutField(path) ? 'Timeout (seconds)' : path
}

function LocatorTargetFields({ value, disabled, onChange, prefix = '' }: { value: LocatorValue; disabled: boolean; onChange: (value: LocatorValue) => void; prefix?: string }) {
  const strategy = String(value.strategy ?? 'label')
  const changeStrategy = (next: string) => {
    const defaults: Record<string, LocatorValue> = {
      label: { strategy: 'label', label: '', exact: true },
      role: { strategy: 'role', role: 'button', name: '', exact: true },
      css: { strategy: 'css', selector: '', exact: true },
      text: { strategy: 'text', text: '', exact: true },
    }
    onChange(defaults[next])
  }
  return <div className="locator-fields">
    <label>{prefix}Strategy <Help text="How Playwright locates the element. Prefer Label or Role; use CSS only when accessible locators are unavailable."/>
      <select disabled={disabled} value={strategy} onChange={(e) => changeStrategy(e.target.value)}><option value="label">Label</option><option value="role">Role</option><option value="text">Visible text</option><option value="css">CSS selector</option></select>
    </label>
    {strategy === 'label' && <label>{prefix}Label <Help text="The visible label associated with a form control, for example Email address."/><input disabled={disabled} value={String(value.label ?? '')} placeholder="Email address" onChange={(e) => onChange({ ...value, label: e.target.value })}/></label>}
    {strategy === 'role' && <><label>{prefix}Role <Help text="The accessible role, such as button, textbox, checkbox, link, or combobox."/><input disabled={disabled} value={String(value.role ?? '')} placeholder="button" onChange={(e) => onChange({ ...value, role: e.target.value })}/></label><label>{prefix}Accessible name <Help text="The element's accessible name, usually its visible text or aria-label."/><input disabled={disabled} value={String(value.name ?? '')} placeholder="Submit" onChange={(e) => onChange({ ...value, name: e.target.value })}/></label></>}
    {strategy === 'text' && <label>{prefix}Visible text <Help text="Text visibly rendered inside the target element."/><input disabled={disabled} value={String(value.text ?? '')} placeholder="Success" onChange={(e) => onChange({ ...value, text: e.target.value })}/></label>}
    {strategy === 'css' && <label>{prefix}CSS selector <Help text="A CSS selector only, for example #username or [data-testid='save']. XPath and JavaScript are rejected."/><input disabled={disabled} value={String(value.selector ?? '')} placeholder="#username" onChange={(e) => onChange({ ...value, selector: e.target.value })}/></label>}
    <label className="inline-field"><input disabled={disabled} type="checkbox" checked={value.exact !== false} onChange={(e) => onChange({ ...value, exact: e.target.checked })}/> Exact match <Help text="When enabled, the label, name, or text must match exactly instead of partially."/></label>
  </div>
}

function LocatorEditor({ value, disabled, onChange }: { value: unknown; disabled: boolean; onChange: (value: LocatorValue) => void }) {
  const locator = value && typeof value === 'object' && !Array.isArray(value) ? value as LocatorValue : { strategy: 'label', label: '', exact: true }
  const match = String(locator.match ?? 'strict')
  const scope = locator.scope && typeof locator.scope === 'object' ? locator.scope as LocatorValue : undefined
  return <div className="locator-editor">
    <LocatorTargetFields value={locator} disabled={disabled} onChange={(target) => onChange({ ...target, match: locator.match ?? 'strict', ...(locator.nth === undefined ? {} : { nth: locator.nth }), ...(scope ? { scope } : {}) })}/>
    <label>Match mode <Help text="Strict requires exactly one match. First, Last, or Nth must be selected explicitly when multiple elements are expected."/>
      <select disabled={disabled} value={match} onChange={(e) => onChange({ ...locator, match: e.target.value, ...(e.target.value === 'nth' ? { nth: Number(locator.nth ?? 0) } : { nth: undefined }) })}><option value="strict">Strict (unique)</option><option value="first">First</option><option value="last">Last</option><option value="nth">Nth</option></select>
    </label>
    {match === 'nth' && <label>Nth index <Help text="Zero-based index: 0 is the first matching element. Values are limited to 0–99."/><input disabled={disabled} type="number" min="0" max="99" value={Number(locator.nth ?? 0)} onChange={(e) => onChange({ ...locator, nth: Number(e.target.value) })}/></label>}
    <label className="inline-field"><input disabled={disabled} type="checkbox" checked={Boolean(scope)} onChange={(e) => onChange(e.target.checked ? { ...locator, scope: { strategy: 'css', selector: '.container', exact: true } } : { ...locator, scope: undefined })}/> Limit to a scope <Help text="Optionally find a container first, then search for the target only inside that container."/></label>
    {scope && <fieldset><legend>Scope locator</legend><LocatorTargetFields prefix="Scope " value={scope} disabled={disabled} onChange={(next) => onChange({ ...locator, scope: next })}/></fieldset>}
  </div>
}

function SelectOptionEditor({ value, disabled, onChange }: { value: unknown; disabled: boolean; onChange: (value: unknown) => void }) {
  const option = value && typeof value === 'object' ? value as Record<string, unknown> : { by: 'label', value: '' }
  const by = String(option.by ?? 'label')
  return <div className="select-option-editor"><label>Choose option by <Help text="Select by visible label, submitted value, or zero-based index. No automatic fallback is used."/><select disabled={disabled} value={by} onChange={(e) => onChange({ by: e.target.value, value: e.target.value === 'index' ? 0 : '' })}><option value="label">Visible label</option><option value="value">HTML value</option><option value="index">Index</option></select></label><label>Option {by}<Help text={by === 'index' ? 'Zero-based option index.' : `Exact ${by} passed to Playwright.`}/><input disabled={disabled} type={by === 'index' ? 'number' : 'text'} min={by === 'index' ? 0 : undefined} value={String(option.value ?? '')} onChange={(e) => onChange({ ...option, value: by === 'index' ? Number(e.target.value) : e.target.value })}/></label></div>
}

function TicketFields({ value, disabled, onChange }: { value: unknown; disabled: boolean; onChange: (value: unknown) => void }) {
  const rows = Array.isArray(value) ? value as Array<Record<string, unknown>> : []
  const update = (index: number, patch: Record<string, unknown>) => onChange(rows.map((row, i) => i === index ? { ...row, ...patch } : row))
  return <div className="ticket-fields">
    {rows.map((row, index) => <div className="ticket-row" key={index}>
      <strong>Field {index + 1} target</strong>
      <LocatorEditor disabled={disabled} value={row.target} onChange={(target) => update(index, { target })}/>
      <select disabled={disabled} aria-label={`Field ${index + 1} control`} value={String(row.control_type ?? 'text')} onChange={(e) => update(index, { control_type: e.target.value, ...(e.target.value === 'select' ? { option: { by: 'label', value: '' } } : { option: undefined }) })}><option>text</option><option>textarea</option><option>select</option></select>
      {row.control_type === 'select' ? <><select disabled={disabled} value={String((row.option as Record<string, unknown>)?.by ?? 'label')} onChange={(e) => update(index, { option: { ...(row.option as object), by: e.target.value } })}><option>label</option><option>value</option><option>index</option></select><input disabled={disabled} value={String((row.option as Record<string, unknown>)?.value ?? '')} onChange={(e) => update(index, { option: { ...(row.option as object), value: (row.option as Record<string, unknown>)?.by === 'index' ? Number(e.target.value) : e.target.value } })}/></> : <input disabled={disabled} placeholder="Value" value={String(row.value ?? '')} onChange={(e) => update(index, { value: e.target.value })}/>} 
      <button disabled={disabled} onClick={() => onChange(rows.filter((_, i) => i !== index))}>Remove</button>
    </div>)}
    <button disabled={disabled} onClick={() => onChange([...rows, { target: { strategy: 'label', label: 'Field label', exact: true }, control_type: 'text', value: '' }])}>Add field</button>
  </div>
}

export function Inspector({ node, stepType, readOnly, onChange }: Props) {
  const [advanced, setAdvanced] = useState('')
  const [jsonError, setJsonError] = useState('')
  useEffect(() => { setAdvanced(JSON.stringify(node?.data.args ?? {}, null, 2)); setJsonError('') }, [node?.id, node?.data.args])
  if (!node) return <aside className="inspector"><h2>Inspector</h2><p>Select a node.</p></aside>
  if (node.data.kind === 'start') return <aside className="inspector"><h2>Start</h2><p>The required entry point cannot be deleted.</p></aside>
  if (node.data.kind === 'comment') return <aside className="inspector"><h2>Comment</h2><textarea disabled={readOnly} value={node.data.text ?? ''} onChange={(e) => onChange({ ...node.data, text: e.target.value })}/></aside>
  const args = node.data.args ?? {}
  const fields = stepType?.editor_schema.fields ?? []
  const changeArg = (key: string, value: unknown) => onChange({ ...node.data, args: { ...args, [key]: value } })
  return <aside className="inspector">
    <h2>{stepType?.name ?? node.data.step_type}</h2><p>{stepType?.description}</p>
    {fields.map((field) => <label key={field.path}>{fieldLabel(field.path)}
      {field.widget === 'ticket-fields' ? <TicketFields disabled={readOnly} value={args[field.path]} onChange={(value) => changeArg(field.path, value)}/>
        : field.widget === 'locator' ? <LocatorEditor disabled={readOnly} value={args[field.path]} onChange={(value) => changeArg(field.path, value)}/>
          : field.widget === 'select-option' ? <SelectOptionEditor disabled={readOnly} value={args[field.path]} onChange={(value) => changeArg(field.path, value)}/>
          : typeof args[field.path] === 'boolean' ? <input disabled={readOnly} type="checkbox" checked={Boolean(args[field.path])} onChange={(e) => changeArg(field.path, e.target.checked)}/>
            : isNumericField(stepType, field.path, args[field.path]) ? <input disabled={readOnly} type="number" step={isSecondsTimeoutField(field.path) ? 0.1 : getSchemaProperty(stepType, field.path)?.type === 'integer' ? 1 : 'any'} value={toDisplayNumber(field.path, args[field.path])} onChange={(e) => changeArg(field.path, fromDisplayNumber(field.path, e.target.value))}/>
              : <input disabled={readOnly} value={String(args[field.path] ?? '')} onChange={(e) => changeArg(field.path, e.target.value)}/>} 
      {isSecondsTimeoutField(field.path) && <small className="field-hint">Displayed in seconds, stored as milliseconds.</small>}
    </label>)}
    <details><summary>Advanced arguments JSON</summary><textarea aria-label="Advanced arguments JSON" disabled={readOnly} value={advanced} onChange={(e) => setAdvanced(e.target.value)}/><button disabled={readOnly} onClick={() => { try { const parsed = JSON.parse(advanced); if (!parsed || Array.isArray(parsed) || typeof parsed !== 'object') throw new Error('Arguments must be an object'); setJsonError(''); onChange({ ...node.data, args: parsed }) } catch (error) { setJsonError((error as Error).message) } }}>Apply JSON</button>{jsonError && <span className="error">{jsonError}</span>}</details>
  </aside>
}
