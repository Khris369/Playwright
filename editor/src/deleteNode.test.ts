import { describe, expect, it } from 'vitest'
import { deletionReplacementSlots, removeNode, removeNodes, splitEdgeWithNode } from './graph'
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

    expect(removeNodes(nodes, edges, ['middle']).nodes).toEqual([nodes[0], nodes[2]])
    expect(removeNodes(nodes, edges, ['middle']).edges).toEqual([expect.objectContaining({ source: 'start', target: 'end' })])
  })

  it('bridges two consecutive deleted steps', () => {
    const nodes = chain(['1', '2', '3', '4'])
    const edges = chainEdges(nodes)
    const result = removeNodes(nodes, edges, ['2', '3'])
    expect(result.nodes.map((node) => node.id)).toEqual(['1', '4'])
    expect(result.edges.map(({ source, target }) => ({ source, target }))).toEqual([{ source: '1', target: '4' }])
  })

  it('bridges three consecutive deleted steps and separate gaps independently', () => {
    const nodes = chain(['a', 'b', 'c', 'd', 'e', 'f'])
    const edges = chainEdges(nodes)
    const result = removeNodes(nodes, edges, ['b', 'c', 'd', 'e'])
    expect(result.edges.map(({ source, target }) => ({ source, target }))).toEqual([{ source: 'a', target: 'f' }])

    const separate = removeNodes(nodes, edges, ['b', 'd'])
    expect(separate.edges.map(({ source, target }) => ({ source, target }))).toEqual([
      { source: 'a', target: 'c' },
      { source: 'c', target: 'e' },
      { source: 'e', target: 'f' },
    ])
  })

  it('preserves incoming edge metadata and exposes the replacement slot', () => {
    const nodes = chain(['start', 'middle', 'end'])
    nodes[0].data.kind = 'start'
    const edges = [
      { id: 'in', source: 'start', target: 'middle', data: { branch: 'true' as const } },
      { id: 'out', source: 'middle', target: 'end', data: { branch: 'false' as const } },
    ]
    const slots = deletionReplacementSlots(nodes, edges, ['middle'])
    expect(slots).toEqual([{ incoming: edges[0], outgoing: edges[1], source: 'start', target: 'end' }])
    expect(removeNodes(nodes, edges, ['middle']).edges[0].data).toEqual({ branch: 'true' })
  })

  it('does not bridge ambiguous branch deletion or create duplicates/self-loops', () => {
    const nodes = chain(['branch', 'middle', 'left', 'right'])
    nodes[0].data.kind = 'if'
    const edges = [
      { id: 'in', source: 'branch', target: 'middle' },
      { id: 'left', source: 'middle', target: 'left', data: { branch: 'true' as const } },
      { id: 'right', source: 'middle', target: 'right', data: { branch: 'false' as const } },
    ]
    expect(removeNodes(nodes, edges, ['middle']).edges).toEqual([])

    const linearNodes = chain(['x', 'y', 'z'])
    const linearEdges = [{ id: 'existing', source: 'x', target: 'z' }, { id: 'xy', source: 'x', target: 'y' }, { id: 'yz', source: 'y', target: 'z' }]
    expect(removeNodes(linearNodes, linearEdges, ['y']).edges).toEqual([{ id: 'existing', source: 'x', target: 'z' }])
  })

  it('splits the preserved edge in place and keeps edge data', () => {
    const edge = { id: 'bridge', source: '1', target: '4', data: { branch: 'true' as const } }
    const result = splitEdgeWithNode([edge], edge, '6', edge.data, undefined)
    expect(result.map(({ source, target, data }) => ({ source, target, data }))).toEqual([
      { source: '1', target: '6', data: { branch: 'true' } },
      { source: '6', target: '4', data: undefined },
    ])
  })

  it('leaves the final surviving node without an outgoing edge and never deletes Start', () => {
    const nodes = chain(['start', 'one', 'two'])
    nodes[0].data.kind = 'start'
    const result = removeNodes(nodes, chainEdges(nodes), ['one', 'two', 'start'])
    expect(result.nodes.map((node) => node.id)).toEqual(['start'])
    expect(result.edges).toEqual([])
  })
})

function chain(ids: string[]): GraphNode[] {
  return ids.map((id) => ({ id, type: 'workflow', position: { x: 0, y: 0 }, data: { kind: 'step', step_type: 'wait_timeout', args: {} } }))
}

function chainEdges(nodes: GraphNode[]): GraphEdge[] {
  return nodes.slice(1).map((node, index) => ({ id: `${nodes[index].id}-${node.id}`, source: nodes[index].id, target: node.id }))
}
