import { describe, expect, it, vi } from 'vitest'
import { arrange, blankGraph, fromDefinition, linearOrder, rewireOrder, toDefinition } from './graph'
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
    expect(arrange(nodes, edges)[99].position.x).toBe(80 + 99 * 280)
  })

  it('rewires a reordered linear fallback', () => {
    expect(rewireOrder(['start', 'b', 'a']).map((edge) => [edge.source, edge.target])).toEqual([['start', 'b'], ['b', 'a']])
  })
})
