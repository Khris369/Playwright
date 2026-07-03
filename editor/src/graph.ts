import type { Definition, GraphEdge, GraphNode, HandleSide } from './types'

export const uid = () => crypto.randomUUID()

const NODE_WIDTH = 210
const NODE_HEIGHT = 80
const STEP_X = 280
const STEP_Y = 180

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
  const order = linearOrder(nodes, edges)
  const rank = new Map(order.map((id, index) => [id, index]))

  return nodes.map((node) =>
    node.data.kind === 'comment'
      ? node
      : { ...node, position: { x: 80 + (rank.get(node.id) ?? 0) * STEP_X, y: 160 } },
  )
}

export function rewireOrder(order: string[]): GraphEdge[] {
  return order.slice(1).map((target, index) => ({
    id: uid(),
    source: order[index],
    target,
  }))
}

export function removeNode(nodes: GraphNode[], edges: GraphEdge[], nodeId: string): { nodes: GraphNode[]; edges: GraphEdge[] } {
  const node = nodes.find((item) => item.id === nodeId)
  if (!node || node.data.kind === 'start') return { nodes, edges }

  return {
    nodes: nodes.filter((item) => item.id !== nodeId),
    edges: edges.filter((edge) => edge.source !== nodeId && edge.target !== nodeId),
  }
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
