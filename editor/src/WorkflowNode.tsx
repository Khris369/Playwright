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

export function WorkflowNode({ id, data, selected }: NodeProps<GraphNode>) {
  const updateNodeInternals = useUpdateNodeInternals()
  const summary = data.kind === 'step' ? JSON.stringify(data.args ?? {}).slice(0, 90) : data.text ?? ''

  useEffect(() => {
    updateNodeInternals(id)
  }, [data.source_handle, data.target_handle, id, updateNodeInternals])

  return (
    <div className={`workflow-node ${selected ? 'selected' : ''} ${data.errors?.length ? 'invalid' : ''} ${data.runState ?? ''}`}>
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
