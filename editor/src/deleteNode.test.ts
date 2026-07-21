import { describe, expect, it } from 'vitest'
import { removeNode, removeNodes, replacementEdgesForNode } from './graph'
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

  it('removes every incident edge when keyboard deletion removes multiple nodes', () => {
    const nodes: GraphNode[] = [
      { id: 'start', type: 'workflow', position: { x: 0, y: 0 }, data: { kind: 'start' }, deletable: false },
      { id: 'middle', type: 'workflow', position: { x: 100, y: 0 }, data: { kind: 'step', step_type: 'wait_timeout', args: {} } },
      { id: 'end', type: 'workflow', position: { x: 200, y: 0 }, data: { kind: 'step', step_type: 'wait_timeout', args: {} } },
    ]
    const edges: GraphEdge[] = [
      { id: 'incoming', source: 'start', target: 'middle' },
      { id: 'outgoing', source: 'middle', target: 'end' },
    ]

    expect(removeNodes(nodes, edges, ['middle'])).toEqual({ nodes: [nodes[0], nodes[2]], edges: [] })
    expect(replacementEdgesForNode(nodes, edges, 'middle')).toEqual({ incoming: edges[0], outgoing: edges[1] })
  })
})
