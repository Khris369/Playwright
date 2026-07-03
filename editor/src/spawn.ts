import type { GraphNode } from './types'

type XYPosition = { x: number; y: number }

const NODE_WIDTH = 210
const NODE_HEIGHT = 80
const STEP_X = 280
const STEP_Y = 180

const OFFSETS: Array<[number, number]> = [
  [0, 0],
  [-1, 0],
  [1, 0],
  [0, -1],
  [0, 1],
  [-1, -1],
  [1, -1],
  [-1, 1],
  [1, 1],
  [-2, 0],
  [2, 0],
  [0, -2],
  [0, 2],
]

export function spawnNodePosition(nodes: GraphNode[], anchor: XYPosition): XYPosition {
  const occupied = nodes.filter((node) => node.data.kind !== 'comment')

  for (const [offsetX, offsetY] of OFFSETS) {
    const position = {
      x: anchor.x - NODE_WIDTH / 2 + offsetX * STEP_X,
      y: anchor.y - NODE_HEIGHT / 2 + offsetY * STEP_Y,
    }

    const overlaps = occupied.some((node) => {
      const width = node.width ?? NODE_WIDTH
      const height = node.height ?? NODE_HEIGHT
      return (
        position.x < node.position.x + width &&
        position.x + NODE_WIDTH > node.position.x &&
        position.y < node.position.y + height &&
        position.y + NODE_HEIGHT > node.position.y
      )
    })

    if (!overlaps) return position
  }

  return {
    x: anchor.x - NODE_WIDTH / 2,
    y: anchor.y - NODE_HEIGHT / 2,
  }
}
