import { describe, expect, it } from 'vitest'
import { spawnNodePosition } from './spawn'
import type { GraphNode } from './types'

function node(id: string, x: number, y: number): GraphNode {
  return {
    id,
    type: 'workflow',
    position: { x, y },
    data: { kind: 'step', step_type: 'wait_timeout', args: {} },
  }
}

describe('spawnNodePosition', () => {
  it('centers a new node when the canvas is empty', () => {
    expect(spawnNodePosition([], { x: 500, y: 300 })).toEqual({ x: 395, y: 260 })
  })

  it('moves to the nearest open slot around the anchor', () => {
    const occupied = [node('a', 395, 260)]
    expect(spawnNodePosition(occupied, { x: 500, y: 300 })).toEqual({ x: 115, y: 260 })
  })
})
