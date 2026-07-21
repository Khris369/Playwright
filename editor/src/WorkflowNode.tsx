import { useEffect } from 'react'
import { Handle, Position, useUpdateNodeInternals, type NodeProps } from '@xyflow/react'
import type { GraphNode, HandleSide } from './types'

const sideToPosition: Record<HandleSide, Position> = {
  top: Position.Top,
  right: Position.Right,
  bottom: Position.Bottom,
  left: Position.Left,
}

function renderHandle(kind: 'source' | 'target', side: HandleSide | undefined) {
  if (!side) return null
  return <Handle className={`workflow-handle workflow-handle-${kind}-${side}`} id={`${kind}-${side}`} type={kind} position={sideToPosition[side]} />
}

const stateLabels: Record<string, string> = {
  attached: 'Attached to DOM', visible: 'Visible', hidden: 'Not visible or absent', detached: 'Detached from DOM',
  enabled: 'Enabled', disabled: 'Disabled', editable: 'Editable', not_editable: 'Not editable', checked: 'Checked', unchecked: 'Unchecked',
}

function targetSummary(args: Record<string, unknown>): string {
  const target = args.target as Record<string, unknown> | undefined
  if (!target) return ''
  if (target.strategy === 'role') return String(target.name ?? target.role ?? '')
  if (target.strategy === 'label') return String(target.label ?? '')
  if (target.strategy === 'text') return `“${String(target.text ?? '')}”`
  return String(target.selector ?? '')
}

function stepSummary(stepType: string | undefined, args: Record<string, unknown>): string {
  if (stepType !== 'wait_for_element' && stepType !== 'verify_element') return JSON.stringify(args).slice(0, 90)
  const state = String(args[stepType === 'verify_element' ? 'expected_state' : 'state'] ?? 'visible')
  const timeout = typeof args.timeout_ms === 'number' ? `${args.timeout_ms / 1000}s` : ''
  return `${targetSummary(args)} · ${stepType === 'verify_element' ? 'Expected' : 'Until'}: ${stateLabels[state] ?? state}${timeout ? ` · ${timeout}` : ''}`
}

export function WorkflowNode({ id, data, selected }: NodeProps<GraphNode>) {
  const updateNodeInternals = useUpdateNodeInternals()
  const summary = data.kind === 'step' ? stepSummary(data.step_type, data.args ?? {}) : data.text ?? ''

  useEffect(() => {
    updateNodeInternals(id)
  }, [data.source_handle, data.target_handle, id, updateNodeInternals])

  return (
    <div className={`workflow-node ${selected || data.sequenceSelected ? 'selected' : ''} ${data.errors?.length ? 'invalid' : ''} ${data.runState ?? ''}`}>
      {data.kind !== 'comment' && renderHandle('target', data.target_handle)}
      {data.kind === 'if' ? <><Handle id="true" type="source" position={Position.Right} style={{ top: '35%' }} /><Handle id="false" type="source" position={Position.Right} style={{ top: '70%' }} /></> : data.kind === 'loop' ? <><Handle id="body" type="source" position={Position.Right} style={{ top: '35%' }} /><Handle id="done" type="source" position={Position.Right} style={{ top: '70%' }} /></> : data.kind !== 'comment' && renderHandle('source', data.source_handle)}
      <div className="node-kind">{data.kind}</div>
      <strong>{data.kind === 'start' ? 'Start' : data.kind === 'comment' ? 'Comment' : data.title ?? data.step_type}</strong>
      {data.kind === 'if' && <small>TRUE / FALSE</small>}
      {data.kind === 'loop' && <small>BODY / DONE</small>}
      <small>{summary}</small>
      {data.errors?.map((error) => <span className="node-error" key={error}>{error}</span>)}
      {data.runState && <span className="run-state">{data.runState}</span>}
    </div>
  )
}
