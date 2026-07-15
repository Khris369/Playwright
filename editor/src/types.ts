import type { Edge, Node, Viewport } from '@xyflow/react'

export type HandleSide = 'top' | 'right' | 'bottom' | 'left'

export type StepType = {
  key: string
  name: string
  category: string
  description: string
  default_args: Record<string, unknown>
  args_schema: Record<string, unknown>
  editor_schema: { fields?: Array<{ path: string; widget: string }> }
}

export type GraphNodeData = {
  kind: 'start' | 'step' | 'if' | 'loop' | 'comment'
  step_type?: string
  args?: Record<string, unknown>
  text?: string
  title?: string
  errors?: string[]
  runState?: string
  sequenceSelected?: boolean
  source_handle?: HandleSide
  target_handle?: HandleSide
}

export type GraphNode = Node<GraphNodeData>
export type GraphEdgeData = { branch?: 'true' | 'false' | 'body' | 'done' }
export type GraphEdge = Edge<GraphEdgeData>

export type Definition = {
  schema_version: 2
  graph: {
    nodes: Array<Record<string, unknown>>
    edges: Array<Record<string, unknown>>
    viewport: Viewport
  }
}

export type Version = {
  id: number
  workflow_id: number
  version_number: number
  is_published: boolean
  definition_json: Definition
  lock_version: number
}

export type ValidationResult = {
  valid: boolean
  compiled_order: string[]
  errors: Array<{ code: string; message: string; node_id?: string; edge_id?: string }>
}
