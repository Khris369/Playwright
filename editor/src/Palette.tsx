import { useMemo, useState } from 'react'
import type { StepType } from './types'

export function Palette({ stepTypes, disabled, onAdd, onControl = () => undefined, onComment }: { stepTypes: StepType[]; disabled: boolean; onAdd: (step: StepType) => void; onControl?: (kind: 'if' | 'loop') => void; onComment: () => void }) {
  const [search, setSearch] = useState('')
  const groups = useMemo(() => stepTypes.filter((step) => `${step.name} ${step.description}`.toLowerCase().includes(search.toLowerCase())).reduce((map, step) => map.set(step.category, [...(map.get(step.category) ?? []), step]), new Map<string, StepType[]>()), [stepTypes, search])
  return <aside className="palette"><h2>Nodes</h2><input aria-label="Search nodes" placeholder="Search" value={search} onChange={(e) => setSearch(e.target.value)}/>
    {[...groups].map(([category, steps]) => <section key={category}><h3>{category}</h3>{steps.map((step) => <button disabled={disabled} key={step.key} onClick={() => onAdd(step)}><strong>{step.name}</strong><small>{step.description}</small></button>)}</section>)}
    <section><h3>Control flow</h3><button disabled={disabled} onClick={() => onControl('if')}><strong>If</strong><small>Choose a branch from a state value.</small></button><button disabled={disabled} onClick={() => onControl('loop')}><strong>Loop</strong><small>Repeat until a condition or iteration limit.</small></button></section>
    <section><h3>Annotation</h3><button disabled={disabled} onClick={onComment}>Comment</button></section>
  </aside>
}
