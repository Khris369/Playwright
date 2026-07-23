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
    const arranged = arrange(nodes, edges, { mode: 'all' })
    expect(arranged[99].position.x).toBeGreaterThan(arranged[0].position.x)
    expect(arranged[99].position.y).toBe(arranged[0].position.y)
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
    ], { mode: 'all' })
    const yes = arranged.find((node) => node.id === 'yes')!
    const no = arranged.find((node) => node.id === 'no')!
    expect(yes.position.x).toBeLessThan(no.position.x)
    expect(yes.position.y).not.toBe(no.position.y)
  })

  it('keeps a clean layout unchanged in tidy mode', () => {
    const nodes: GraphNode[] = [
      { id: 'start', type: 'workflow', position: { x: 10, y: 20 }, data: { kind: 'start' } },
      { id: 'step', type: 'workflow', position: { x: 400, y: 20 }, data: { kind: 'step' } },
      { id: 'comment', type: 'workflow', position: { x: 50, y: 50 }, data: { kind: 'comment', text: 'note' } },
    ]
    const result = arrange(nodes, [{ id: 'e', source: 'start', target: 'step' }], { mode: 'tidy' })
    expect(result.map((node) => node.position)).toEqual(nodes.map((node) => node.position))
  })

  it('arranges only the selected executable nodes', () => {
    const nodes: GraphNode[] = [
      { id: 'start', type: 'workflow', position: { x: 0, y: 0 }, data: { kind: 'start' } },
      { id: 'a', type: 'workflow', position: { x: 500, y: 300 }, data: { kind: 'step' } },
      { id: 'b', type: 'workflow', position: { x: 500, y: 500 }, data: { kind: 'step' } },
      { id: 'fixed', type: 'workflow', position: { x: 900, y: 900 }, data: { kind: 'step' } },
    ]
    const result = arrange(nodes, [{ id: 'a-b', source: 'a', target: 'b' }], { mode: 'selected', selectedNodeIds: new Set(['a', 'b']) })
    expect(result.find((node) => node.id === 'fixed')?.position).toEqual(nodes[3].position)
    expect(result.find((node) => node.id === 'b')?.position).not.toEqual(nodes[2].position)
  })

  it('tidies an overlap locally without applying global rank positions', () => {
    const nodes: GraphNode[] = [
      { id: '1', type: 'workflow', position: { x: 0, y: 0 }, data: { kind: 'start' } },
      { id: '2', type: 'workflow', position: { x: 500, y: 260 }, data: { kind: 'step' } },
      { id: '3', type: 'workflow', position: { x: 1000, y: 520 }, data: { kind: 'step' } },
      { id: '4', type: 'workflow', position: { x: 1500, y: 780 }, data: { kind: 'step' } },
      { id: '5', type: 'workflow', position: { x: 1500, y: 780 }, data: { kind: 'step' } },
    ]
    const result = arrange(nodes, [
      { id: '1-2', source: '1', target: '2' }, { id: '2-3', source: '2', target: '3' },
      { id: '3-4', source: '3', target: '4' }, { id: '4-5', source: '4', target: '5' },
    ], { mode: 'tidy' })
    expect(result.find((node) => node.id === '1')?.position).toEqual(nodes[0].position)
    expect(result.find((node) => node.id === '2')?.position).toEqual(nodes[1].position)
    expect(result.find((node) => node.id === '3')?.position).toEqual(nodes[2].position)
    const changedLocalNodes = result.slice(3).filter((node, index) => node.position.x !== nodes[index + 3].position.x || node.position.y !== nodes[index + 3].position.y)
    expect(changedLocalNodes).toHaveLength(1)
  })

  it('preserves vertical and backward local directions while tidying', () => {
    const vertical: GraphNode[] = [
      { id: 'a', type: 'workflow', position: { x: 0, y: 0 }, data: { kind: 'start' } },
      { id: 'b', type: 'workflow', position: { x: 0, y: 170 }, data: { kind: 'step' } },
    ]
    const verticalResult = arrange(vertical, [{ id: 'a-b', source: 'a', target: 'b' }], { mode: 'tidy' })
    expect(verticalResult[0].position.x).toBe(verticalResult[1].position.x)
    expect(verticalResult[0].position.y).toBeLessThan(verticalResult[1].position.y)

    const backward: GraphNode[] = [
      { id: 'a', type: 'workflow', position: { x: 400, y: 0 }, data: { kind: 'start' } },
      { id: 'b', type: 'workflow', position: { x: 100, y: 0 }, data: { kind: 'step' } },
    ]
    const backwardResult = arrange(backward, [{ id: 'a-b', source: 'a', target: 'b' }], { mode: 'tidy' })
    expect(backwardResult[0].position.x).toBeGreaterThan(backwardResult[1].position.x)
  })

  it('uses measured variable dimensions instead of fallback spacing', () => {
    const nodes: GraphNode[] = [
      { id: 'wide', type: 'workflow', position: { x: 0, y: 0 }, data: { kind: 'start' } },
      { id: 'short', type: 'workflow', position: { x: 250, y: 0 }, data: { kind: 'step' } },
    ]
    const dimensions = new Map([
      ['wide', { width: 400, height: 100 }],
      ['short', { width: 100, height: 60 }],
    ])
    const result = arrange(nodes, [{ id: 'wide-short', source: 'wide', target: 'short' }], { mode: 'tidy', nodeDimensions: dimensions })
    const wide = result[0].position; const short = result[1].position
    expect(wide.x + 400 + 48 <= short.x || short.x + 100 + 48 <= wide.x || Math.abs(wide.y - short.y) >= 100 + 36).toBe(true)
  })

  it('rearranges selected geometry and leaves comments and metadata untouched', () => {
    const nodes: GraphNode[] = [
      { id: 'a', type: 'workflow', position: { x: 0, y: 0 }, data: { kind: 'step', title: 'A', args: { value: 1 } } },
      { id: 'b', type: 'workflow', position: { x: 250, y: 170 }, data: { kind: 'step', title: 'B', args: { value: 2 } } },
      { id: 'comment', type: 'workflow', position: { x: 30, y: 30 }, data: { kind: 'comment', text: 'fixed' } },
    ]
    const edges = [{ id: 'a-b', source: 'a', target: 'b' }]
    const before = structuredClone(nodes)
    const result = arrange(nodes, edges, { mode: 'selected', selectedNodeIds: new Set(['a', 'b']) })
    expect(result[1].position.x).toBeGreaterThan(result[0].position.x)
    expect(result[1].position.y).toBe(result[0].position.y)
    expect(result[2]).toEqual(nodes[2])
    expect(nodes).toEqual(before)
    expect(edges).toEqual([{ id: 'a-b', source: 'a', target: 'b' }])
  })

  it('keeps disconnected selected nodes in their arrangement and is deterministic', () => {
    const nodes: GraphNode[] = [
      { id: 'a', type: 'workflow', position: { x: 0, y: 0 }, data: { kind: 'step' } },
      { id: 'b', type: 'workflow', position: { x: 0, y: 170 }, data: { kind: 'step' } },
    ]
    const options = { mode: 'selected' as const, selectedNodeIds: new Set(['a', 'b']) }
    const first = arrange(nodes, [], options); const second = arrange(nodes, [], options)
    expect(first).toEqual(second)
    expect(first[0].position.x).toBe(first[1].position.x)
    expect(first[0].position.y).toBeLessThan(first[1].position.y)
  })

  it('supports an all-node four-column snake arrangement', () => {
    const nodes: GraphNode[] = Array.from({ length: 6 }, (_, index) => ({ id: String(index), type: 'workflow', position: { x: 100, y: 100 }, data: { kind: index === 0 ? 'start' : 'step' } }))
    const edges = Array.from({ length: 5 }, (_, index) => ({ id: `e${index}`, source: String(index), target: String(index + 1) }))
    const allIds = new Set(nodes.map((node) => node.id))
    const dimensions = new Map(nodes.map((node) => [node.id, { width: 210, height: 80 }] as const))
    const result = arrange(nodes, edges, { mode: 'selected', selectedNodeIds: allIds, columns: 4, snake: true, nodeDimensions: dimensions })
    expect(result[4].position.x).toBe(result[3].position.x)
    expect(result[5].position.x).toBe(result[2].position.x)

    const straight = arrange(nodes, edges, { mode: 'selected', selectedNodeIds: allIds, columns: 4, snake: false, nodeDimensions: dimensions })
    expect(straight[4].position.x).toBe(straight[0].position.x)
  })

  it('rewires a reordered linear fallback', () => {
    expect(rewireOrder(['start', 'b', 'a']).map((edge) => [edge.source, edge.target])).toEqual([['start', 'b'], ['b', 'a']])
  })

  it('rejects a connection from a node to itself', () => {
    expect(isValidConnection({ source: 'a', target: 'a' })).toBe(false)
    expect(isValidConnection({ source: 'a', target: 'b' })).toBe(true)
  })
})
