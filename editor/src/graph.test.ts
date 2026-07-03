import { describe, expect, it, vi } from 'vitest'
import { arrange, blankGraph, fromDefinition, isValidConnection, linearOrder, rewireOrder, toDefinition } from './graph'
import type { GraphNode } from './types'

describe('graph utilities', () => {
  it('round trips a graph and keeps stable node ids', () => {
    vi.stubGlobal('crypto', { randomUUID: () => '00000000-0000-4000-8000-000000000001' })
    const graph = blankGraph(); const definition = toDefinition(graph.nodes, graph.edges)
    expect(fromDefinition(definition).nodes[0].id).toBe(graph.nodes[0].id)
  })

  it('arranges a 100-node workflow deterministically', () => {
    const nodes: GraphNode[] = Array.from({ length: 100 }, (_, index) => ({ id: String(index), type: 'workflow', position: { x: 0, y: 0 }, data: { kind: index ? 'step' : 'start', step_type: index ? 'wait_timeout' : undefined, args: index ? { timeout_ms: 1 } : undefined } }))
    const edges = Array.from({ length: 99 }, (_, index) => ({ id: `e${index}`, source: String(index), target: String(index + 1) }))
    expect(linearOrder(nodes, edges)).toHaveLength(100)
    const arranged = arrange(nodes, edges)
    expect(arranged[99].position.x).toBe(190 + 3 * 250)
    expect(arranged[99].position.y).toBeGreaterThan(arranged[0].position.y)
  })

  it('places branches in compact vertical lanes and ignores loop-back ranking', () => {
    const nodes: GraphNode[] = [
      { id: 'start', type: 'workflow', position: { x: 0, y: 0 }, data: { kind: 'start' } },
      { id: 'if', type: 'workflow', position: { x: 0, y: 0 }, data: { kind: 'if', args: {} } },
      { id: 'yes', type: 'workflow', position: { x: 0, y: 0 }, data: { kind: 'step', step_type: 'wait_timeout' } },
      { id: 'no', type: 'workflow', position: { x: 0, y: 0 }, data: { kind: 'step', step_type: 'wait_timeout' } },
    ]
    const arranged = arrange(nodes, [
      { id: 'a', source: 'start', target: 'if' },
      { id: 'b', source: 'if', target: 'yes' },
      { id: 'c', source: 'if', target: 'no' },
      { id: 'd', source: 'yes', target: 'if' },
    ])
    const yes = arranged.find((node) => node.id === 'yes')!
    const no = arranged.find((node) => node.id === 'no')!
    expect(yes.position.x).toBe(no.position.x)
    expect(yes.position.y).not.toBe(no.position.y)
  })

  it('rewires a reordered linear fallback', () => {
    expect(rewireOrder(['start', 'b', 'a']).map((edge) => [edge.source, edge.target])).toEqual([['start', 'b'], ['b', 'a']])
  })

  it('rejects a connection from a node to itself', () => {
    expect(isValidConnection({ source: 'a', target: 'a' })).toBe(false)
    expect(isValidConnection({ source: 'a', target: 'b' })).toBe(true)
  })
})
