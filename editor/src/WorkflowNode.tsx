import { Handle, Position, type NodeProps } from '@xyflow/react'
import type { GraphNode } from './types'

export function WorkflowNode({ data, selected }: NodeProps<GraphNode>) {
  const summary = data.kind === 'step' ? JSON.stringify(data.args ?? {}).slice(0, 90) : data.text ?? ''
  return <div className={`workflow-node ${selected ? 'selected' : ''} ${data.errors?.length ? 'invalid' : ''} ${data.runState ?? ''}`}>
    {data.kind !== 'start' && data.kind !== 'comment' && <Handle type="target" position={Position.Left}/>} 
    <div className="node-kind">{data.kind}</div>
    <strong>{data.kind === 'start' ? 'Start' : data.kind === 'comment' ? 'Comment' : data.title ?? data.step_type}</strong>
    <small>{summary}</small>
    {data.errors?.map((error) => <span className="node-error" key={error}>{error}</span>)}
    {data.runState && <span className="run-state">{data.runState}</span>}
    {data.kind !== 'comment' && <Handle type="source" position={Position.Right}/>} 
  </div>
}
