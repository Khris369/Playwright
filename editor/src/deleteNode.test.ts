import { describe, expect, it } from 'vitest'
import { removeNode } from './graph'
import type { GraphEdge, GraphNode } from './types'

describe('removeNode', () => {
  it('removes a node and connected edges, but preserves start nodes', () => {
    const nodes: GraphNode[] = [
      { id: 'start', type: 'workflow', position: { x: 0, y: 0 }, data: { kind: 'start', title: 'Start' }, deletable: false },
      { id: 'step', type: 'workflow', position: { x: 0, y: 0 }, data: { kind: 'step', step_type: 'wait_timeout', args: {} } },
    ]
    const edges: GraphEdge[] = [{ id: 'edge', source: 'start', target: 'step' }]

    expect(removeNode(nodes, edges, 'step')).toEqual({ nodes: [nodes[0]], edges: [] })
    expect(removeNode(nodes, edges, 'start')).toEqual({ nodes, edges })
  })
})
