import type { Definition, GraphEdge, GraphNode, HandleSide } from './types'

export const uid = () => crypto.randomUUID()

const NODE_WIDTH = 210
const NODE_HEIGHT = 80
const STEP_X = 250
const STEP_Y = 130
const COLUMNS_PER_ROW = 4
const ROW_GAP = 70

export function blankGraph(): { nodes: GraphNode[]; edges: GraphEdge[] } {
  return {
    nodes: [
      {
        id: uid(),
        type: 'workflow',
        position: { x: 80, y: 160 },
        data: { kind: 'start', title: 'Start' },
        deletable: false,
      },
    ],
    edges: [],
  }
}

export function toDefinition(nodes: GraphNode[], edges: GraphEdge[], viewport = { x: 0, y: 0, zoom: 1 }): Definition {
  return {
    schema_version: 2,
    graph: {
      nodes: nodes.map(({ id, position, data }) => {
        if (data.kind === 'step') {
          return {
            id,
            kind: 'step',
            step_type: data.step_type,
            args: data.args ?? {},
            position,
            source_handle: data.source_handle,
            target_handle: data.target_handle,
          }
        }

        if (data.kind === 'comment') {
          return {
            id,
            kind: 'comment',
            text: data.text ?? '',
            position,
          }
        }

        if (data.kind === 'if' || data.kind === 'loop') {
          return { id, kind: data.kind, args: data.args ?? {}, position, target_handle: data.target_handle }
        }

        return {
          id,
          kind: 'start',
          position,
          source_handle: data.source_handle,
          target_handle: data.target_handle,
        }
      }),
      edges: edges.map(({ id, source, target, data }) => ({ id, source, target, ...(data?.branch ? { branch: data.branch } : {}) })),
      viewport,
    },
  }
}

export function fromDefinition(definition: Definition): { nodes: GraphNode[]; edges: GraphEdge[] } {
  return {
    nodes: definition.graph.nodes.map((raw) => {
      const kind = String(raw.kind) as GraphNode['data']['kind']
      return {
        id: String(raw.id),
        type: 'workflow',
        position: raw.position as { x: number; y: number },
        data: {
          kind,
          step_type: raw.step_type as string | undefined,
          args: (raw.args ?? {}) as Record<string, unknown>,
          text: raw.text as string | undefined,
          title: raw.title as string | undefined,
          source_handle: normalizeHandleSide(raw.source_handle),
          target_handle: normalizeHandleSide(raw.target_handle),
        },
        deletable: kind !== 'start',
      }
    }),
    edges: definition.graph.edges.map((raw) => ({
      id: String(raw.id),
      source: String(raw.source),
      target: String(raw.target),
      data: raw.branch ? { branch: raw.branch as 'true' | 'false' | 'body' | 'done' } : undefined,
    })),
  }
}

export function linearOrder(nodes: GraphNode[], edges: GraphEdge[]): string[] {
  const start = nodes.find((node) => node.data.kind === 'start')
  if (!start) return []

  const order = [start.id]
  const seen = new Set<string>(order)
  let current = start.id

  while (true) {
    const outgoing = edges.filter((edge) => edge.source === current)
    if (outgoing.length !== 1) break

    current = outgoing[0].target
    if (seen.has(current)) break

    seen.add(current)
    order.push(current)
  }

  return order
}

export function arrange(nodes: GraphNode[], edges: GraphEdge[]): GraphNode[] {
  const executable = nodes.filter((node) => node.data.kind !== 'comment')
  const start = executable.find((node) => node.data.kind === 'start')
  const rank = new Map<string, number>()
  const queue: string[] = []
  if (start) { rank.set(start.id, 0); queue.push(start.id) }

  while (queue.length) {
    const source = queue.shift()!
    const sourceRank = rank.get(source) ?? 0
    for (const edge of edges.filter((item) => item.source === source)) {
      if (rank.has(edge.target)) continue // Loop-back or already ranked through another path.
      rank.set(edge.target, sourceRank + 1)
      queue.push(edge.target)
    }
  }

  let disconnectedRank = Math.max(0, ...rank.values()) + 1
  for (const node of executable) {
    if (!rank.has(node.id)) rank.set(node.id, disconnectedRank++)
  }

  const columns = new Map<number, GraphNode[]>()
  for (const node of executable) {
    const column = rank.get(node.id) ?? 0
    columns.set(column, [...(columns.get(column) ?? []), node])
  }
  const rowCount = Math.ceil((Math.max(0, ...columns.keys()) + 1) / COLUMNS_PER_ROW)
  const rowLaneCounts = Array.from({ length: rowCount }, (_, row) => {
    const firstColumn = row * COLUMNS_PER_ROW
    return Math.max(1, ...Array.from({ length: COLUMNS_PER_ROW }, (_, offset) => columns.get(firstColumn + offset)?.length ?? 0))
  })
  const rowTops: number[] = []
  let nextTop = 70
  for (const laneCount of rowLaneCounts) {
    rowTops.push(nextTop)
    nextTop += Math.max(80, (laneCount - 1) * STEP_Y + 80) + ROW_GAP
  }

  const position = new Map<string, { x: number; y: number }>()
  for (const [column, columnNodes] of columns) {
    const row = Math.floor(column / COLUMNS_PER_ROW)
    const offset = column % COLUMNS_PER_ROW
    const visualColumn = row % 2 === 0 ? offset : COLUMNS_PER_ROW - 1 - offset
    const rowHeight = Math.max(80, (rowLaneCounts[row] - 1) * STEP_Y + 80)
    const laneHeight = (columnNodes.length - 1) * STEP_Y + 80
    const laneTop = rowTops[row] + (rowHeight - laneHeight) / 2
    columnNodes.forEach((node, index) => position.set(node.id, {
      x: 190 + visualColumn * STEP_X,
      y: laneTop + index * STEP_Y,
    }))
  }

  return nodes.map((node) => node.data.kind === 'comment' ? node : { ...node, position: position.get(node.id) ?? node.position })
}

export function rewireOrder(order: string[]): GraphEdge[] {
  return order.slice(1).map((target, index) => ({
    id: uid(),
    source: order[index],
    target,
  }))
}

export function removeNode(nodes: GraphNode[], edges: GraphEdge[], nodeId: string): { nodes: GraphNode[]; edges: GraphEdge[] } {
  return removeNodes(nodes, edges, [nodeId])
}

/** Remove graph nodes and every edge that references them. Start nodes are protected. */
export function removeNodes(nodes: GraphNode[], edges: GraphEdge[], nodeIds: Iterable<string>): { nodes: GraphNode[]; edges: GraphEdge[] } {
  const requested = new Set(nodeIds)
  const removedIds = new Set(nodes
    .filter((node) => requested.has(node.id) && node.data.kind !== 'start')
    .map((node) => node.id))

  if (!removedIds.size) return { nodes, edges }

  return {
    nodes: nodes.filter((node) => !removedIds.has(node.id)),
    edges: edges.filter((edge) => !removedIds.has(edge.source) && !removedIds.has(edge.target)),
  }
}

/**
 * Return the two edges around a regular step that can be replaced as a single
 * linear slot. Controls are deliberately excluded because their branches need
 * explicit user configuration.
 */
export function replacementEdgesForNode(nodes: GraphNode[], edges: GraphEdge[], nodeId: string): { incoming: GraphEdge; outgoing: GraphEdge } | undefined {
  const node = nodes.find((item) => item.id === nodeId)
  if (!node || node.data.kind !== 'step') return undefined

  const incoming = edges.filter((edge) => edge.target === nodeId)
  const outgoing = edges.filter((edge) => edge.source === nodeId)
  return incoming.length === 1 && outgoing.length === 1 ? { incoming: incoming[0], outgoing: outgoing[0] } : undefined
}

export function defaultNodePosition(index: number): { x: number; y: number } {
  return { x: 80 + index * STEP_X, y: 160 }
}

export function inferSide(from: { x: number; y: number }, to: { x: number; y: number }): HandleSide {
  const dx = to.x - from.x
  const dy = to.y - from.y
  if (Math.abs(dx) >= Math.abs(dy)) return dx >= 0 ? 'right' : 'left'
  return dy >= 0 ? 'bottom' : 'top'
}

export function getOppositeSide(side: HandleSide): HandleSide {
  switch (side) {
    case 'left': return 'right'
    case 'right': return 'left'
    case 'top': return 'bottom'
    case 'bottom': return 'top'
  }
}

export function resolveHandleSide(
  nodes: GraphNode[],
  edges: GraphEdge[],
  node: GraphNode,
  kind: 'source' | 'target',
): HandleSide | undefined {
  const manual = kind === 'source' ? node.data.source_handle : node.data.target_handle
  if (manual) return manual

  if (node.data.kind === 'comment') return undefined
  if (node.data.kind === 'start' && kind === 'target') return undefined

  const connectedIds = kind === 'source'
    ? edges.filter((edge) => edge.source === node.id).map((edge) => edge.target)
    : edges.filter((edge) => edge.target === node.id).map((edge) => edge.source)

  const connectedNodes = connectedIds
    .map((id) => nodes.find((item) => item.id === id))
    .filter((item): item is GraphNode => Boolean(item))

  if (connectedNodes.length > 0) {
    const average = connectedNodes.reduce(
      (acc, connected) => ({
        x: acc.x + connected.position.x,
        y: acc.y + connected.position.y,
      }),
      { x: 0, y: 0 },
    )
    const center = {
      x: average.x / connectedNodes.length,
      y: average.y / connectedNodes.length,
    }
    return inferSide(node.position, center)
  }

  if (kind === 'source') return node.data.kind === 'start' ? 'right' : 'right'
  if (kind === 'target') return node.data.kind === 'start' ? undefined : 'left'
  return undefined
}

export function isValidConnection(connection: { source?: string | null; target?: string | null }): boolean {
  return Boolean(connection.source && connection.target && connection.source !== connection.target)
}

function normalizeHandleSide(value: unknown): HandleSide | undefined {
  return value === 'top' || value === 'right' || value === 'bottom' || value === 'left' ? value : undefined
}
