import type { GraphEdge, GraphNode, Definition } from './types'

export const uid = () => crypto.randomUUID()

export function blankGraph(): { nodes: GraphNode[]; edges: GraphEdge[] } {
  return { nodes: [{ id: uid(), type: 'workflow', position: { x: 80, y: 160 }, data: { kind: 'start', title: 'Start' }, deletable: false }], edges: [] }
}

export function toDefinition(nodes: GraphNode[], edges: GraphEdge[], viewport = { x: 0, y: 0, zoom: 1 }): Definition {
  return {
    schema_version: 2,
    graph: {
      nodes: nodes.map(({ id, position, data }) => data.kind === 'step'
        ? { id, kind: 'step', step_type: data.step_type, args: data.args ?? {}, position }
        : data.kind === 'comment' ? { id, kind: 'comment', text: data.text ?? '', position }
          : { id, kind: 'start', position }),
      edges: edges.map(({ id, source, target }) => ({ id, source, target })),
      viewport,
    },
  }
}

export function fromDefinition(definition: Definition): { nodes: GraphNode[]; edges: GraphEdge[] } {
  const rawNodes = definition.graph.nodes
  return {
    nodes: rawNodes.map((raw) => {
      const kind = String(raw.kind) as 'start' | 'step' | 'comment'
      return {
        id: String(raw.id), type: 'workflow', position: raw.position as { x: number; y: number },
        data: { kind, step_type: raw.step_type as string | undefined, args: (raw.args ?? {}) as Record<string, unknown>, text: raw.text as string | undefined },
        deletable: kind !== 'start',
      }
    }),
    edges: definition.graph.edges.map((raw) => ({ id: String(raw.id), source: String(raw.source), target: String(raw.target) })),
  }
}

export function linearOrder(nodes: GraphNode[], edges: GraphEdge[]): string[] {
  const start = nodes.find((node) => node.data.kind === 'start')
  if (!start) return []
  const order: string[] = []
  const seen = new Set<string>()
  let current: string | undefined = start.id
  while (current && !seen.has(current)) {
    seen.add(current); order.push(current)
    const outgoing = edges.filter((edge) => edge.source === current)
    current = outgoing.length === 1 ? outgoing[0].target : undefined
  }
  return order
}

export function arrange(nodes: GraphNode[], edges: GraphEdge[]): GraphNode[] {
  const order = linearOrder(nodes, edges)
  const rank = new Map(order.map((id, index) => [id, index]))
  let commentIndex = 0
  return nodes.map((node) => node.data.kind === 'comment'
    ? { ...node, position: { x: 80 + commentIndex++ * 260, y: 360 } }
    : { ...node, position: { x: 80 + (rank.get(node.id) ?? 0) * 280, y: 160 } })
}

export function rewireOrder(order: string[]): GraphEdge[] {
  return order.slice(1).map((target, index) => ({ id: uid(), source: order[index], target }))
}
