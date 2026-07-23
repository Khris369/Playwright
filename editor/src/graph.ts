import type { Definition, GraphEdge, GraphNode, HandleSide } from './types'

export const uid = () => crypto.randomUUID()

const STEP_X = 250
export const FALLBACK_NODE_WIDTH = 320
export const FALLBACK_NODE_HEIGHT = 180
const LAYOUT_ORIGIN_X = 190
const LAYOUT_ORIGIN_Y = 70
const RANK_GAP_X = 10
const LANE_GAP_Y = 30
const COMPONENT_GAP_Y = 220
const COLLISION_PADDING_X = 20
const COLLISION_PADDING_Y = 16
const HORIZONTAL_GAP = 10
const VERTICAL_GAP = 28
const MAX_TIDY_PASSES = 12

export type ArrangeMode = 'tidy' | 'selected' | 'all'
export type NodeDimensions = { width: number; height: number }
export interface ArrangeOptions {
  mode: ArrangeMode
  selectedNodeIds?: ReadonlySet<string>
  nodeDimensions?: ReadonlyMap<string, NodeDimensions>
  columns?: number
  snake?: boolean
}

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

export function arrange(nodes: GraphNode[], edges: GraphEdge[], options: ArrangeOptions = { mode: 'tidy' }): GraphNode[] {
  const executable = nodes.filter((node) => node.data.kind !== 'comment')
  const dimensions = options.nodeDimensions ?? new Map<string, NodeDimensions>()
  if (options.mode === 'all') {
    return applyPositions(nodes, calculateFullLayout(executable, edges, dimensions))
  }

  const selectedIds = options.mode === 'selected'
    ? new Set([...options.selectedNodeIds ?? []].filter((id) => executable.some((node) => node.id === id)))
    : new Set(executable.filter((node) => hasLocalCollision(node, executable, dimensions)).map((node) => node.id))
  if (options.mode === 'selected' && selectedIds.size < 2) return nodes
  if (!selectedIds.size) return nodes

  if (options.mode === 'selected') {
    const selected = executable.filter((node) => selectedIds.has(node.id))
    const proposed = calculateSelectedGridLayout(selected, edges, dimensions, options.columns ?? 4, options.snake ?? true)
    return applyPositions(nodes, resolveLocalCollisions(executable, edges, selectedIds, dimensions, proposed))
  }

  return applyPositions(nodes, resolveLocalCollisions(executable, edges, selectedIds, dimensions))
}

function calculateSelectedGridLayout(nodes: GraphNode[], edges: GraphEdge[], dimensions: ReadonlyMap<string, NodeDimensions>, requestedColumns: number, snake: boolean): Map<string, Position> {
  const columns = Math.max(1, Math.min(12, Math.round(requestedColumns)))
  const ids = new Set(nodes.map((node) => node.id)); const index = new Map(nodes.map((node, i) => [node.id, i])); const { outgoing, incoming } = buildAdjacency(edges, ids)
  const rank = new Map<string, number>(); const queue: string[] = []
  const roots = nodes.filter((node) => (incoming.get(node.id) ?? []).length === 0)
  for (const node of [...roots, ...nodes.filter((node) => !roots.includes(node))]) { if (rank.has(node.id)) continue; rank.set(node.id, 0); queue.push(node.id); while (queue.length) { const source = queue.shift()!; const sourceRank = rank.get(source) ?? 0; for (const edge of sortedEdges(outgoing.get(source) ?? [])) { if (rank.has(edge.target)) continue; rank.set(edge.target, sourceRank + 1); queue.push(edge.target) } } }
  const maxRank = Math.max(...rank.values(), 0); let nextRank = maxRank + 1; for (const node of nodes) if (!rank.has(node.id)) rank.set(node.id, nextRank++)
  const byRank = new Map<number, GraphNode[]>(); for (const node of nodes) byRank.set(rank.get(node.id)!, [...(byRank.get(rank.get(node.id)!) ?? []), node])
  const order = new Map(nodes.map((node, i) => [node.id, i])); for (const group of byRank.values()) group.sort((a, b) => order.get(a.id)! - order.get(b.id)! || a.id.localeCompare(b.id))
  const cellWidth = Math.max(...nodes.map((node) => nodeDimension(node, dimensions).width), FALLBACK_NODE_WIDTH) + HORIZONTAL_GAP
  const rowHeights = new Map<number, number>(); for (const [rankValue, group] of byRank) { const row = Math.floor(rankValue / columns); const height = Math.max(...group.map((node) => nodeDimension(node, dimensions).height), FALLBACK_NODE_HEIGHT); rowHeights.set(row, Math.max(rowHeights.get(row) ?? 0, height + VERTICAL_GAP)) }
  const rowTop = new Map<number, number>(); let y = 0; for (let row = 0; row <= Math.floor(maxRank / columns); row++) { rowTop.set(row, y); y += rowHeights.get(row) ?? FALLBACK_NODE_HEIGHT + VERTICAL_GAP }
  const positions = new Map<string, Position>(); for (const [rankValue, group] of byRank) { const row = Math.floor(rankValue / columns); const offset = rankValue % columns; const visualColumn = snake && row % 2 === 1 ? columns - 1 - offset : offset; const x = visualColumn * cellWidth; let laneY = rowTop.get(row) ?? 0; for (const node of group) { positions.set(node.id, { x, y: laneY }); laneY += nodeDimension(node, dimensions).height + VERTICAL_GAP } }
  const currentOrigin = boundingOrigin(nodes); const layoutOrigin = boundingOrigin(nodes, positions); for (const node of nodes) { const position = positions.get(node.id)!; positions.set(node.id, { x: position.x + currentOrigin.x - layoutOrigin.x, y: position.y + currentOrigin.y - layoutOrigin.y }) }
  return positions
}

function boundingOrigin(nodes: GraphNode[], positions?: ReadonlyMap<string, Position>): Position {
  return nodes.reduce((origin, node) => { const position = positions?.get(node.id) ?? node.position; return { x: Math.min(origin.x, position.x), y: Math.min(origin.y, position.y) } }, { x: Number.POSITIVE_INFINITY, y: Number.POSITIVE_INFINITY })
}

function nodeDimension(node: GraphNode, dimensions: ReadonlyMap<string, NodeDimensions>): NodeDimensions {
  const measured = dimensions.get(node.id)
  const width = measured?.width ?? node.measured?.width ?? node.width
  const height = measured?.height ?? node.measured?.height ?? node.height
  return width && width > 0 && height && height > 0 ? { width, height } : { width: FALLBACK_NODE_WIDTH, height: FALLBACK_NODE_HEIGHT }
}

function buildAdjacency(edges: GraphEdge[], ids: ReadonlySet<string>) {
  const outgoing = new Map<string, GraphEdge[]>(); const incoming = new Map<string, GraphEdge[]>()
  for (const id of ids) { outgoing.set(id, []); incoming.set(id, []) }
  for (const edge of edges) {
    if (!ids.has(edge.source) || !ids.has(edge.target)) continue
    outgoing.get(edge.source)!.push(edge); incoming.get(edge.target)!.push(edge)
  }
  return { outgoing, incoming }
}

function branchRank(branch: unknown): number {
  if (branch === 'true' || branch === 'body') return 0
  if (branch === undefined) return 1
  if (branch === 'false' || branch === 'done') return 2
  return 3
}

function sortedEdges(edges: GraphEdge[]): GraphEdge[] {
  return [...edges].sort((a, b) => branchRank(a.data?.branch) - branchRank(b.data?.branch) || String(a.data?.branch ?? '').localeCompare(String(b.data?.branch ?? '')) || a.target.localeCompare(b.target) || a.id.localeCompare(b.id))
}

function stronglyConnectedComponents(nodes: GraphNode[], edges: GraphEdge[]): string[][] {
  const ids = new Set(nodes.map((node) => node.id)); const { outgoing } = buildAdjacency(edges, ids)
  let index = 0; const indices = new Map<string, number>(); const low = new Map<string, number>(); const stack: string[] = []; const onStack = new Set<string>(); const result: string[][] = []
  const visit = (id: string) => {
    indices.set(id, index); low.set(id, index); index++; stack.push(id); onStack.add(id)
    for (const edge of sortedEdges(outgoing.get(id) ?? [])) {
      if (!indices.has(edge.target)) { visit(edge.target); low.set(id, Math.min(low.get(id)!, low.get(edge.target)!)) }
      else if (onStack.has(edge.target)) low.set(id, Math.min(low.get(id)!, indices.get(edge.target)!))
    }
    if (low.get(id) === indices.get(id)) {
      const component: string[] = []; let member = ''
      do { member = stack.pop()!; onStack.delete(member); component.push(member) } while (member !== id)
      result.push(component)
    }
  }
  for (const node of nodes) if (!indices.has(node.id)) visit(node.id)
  return result
}

function calculateFullLayout(nodes: GraphNode[], edges: GraphEdge[], dimensions: ReadonlyMap<string, NodeDimensions>): Map<string, { x: number; y: number }> {
  if (!nodes.length) return new Map()
  const ids = new Set(nodes.map((node) => node.id)); const index = new Map(nodes.map((node, i) => [node.id, i])); const { outgoing } = buildAdjacency(edges, ids)
  const sccs = stronglyConnectedComponents(nodes, edges); const componentOf = new Map<string, number>(); sccs.forEach((component, i) => component.forEach((id) => componentOf.set(id, i)))
  const componentEdges = new Map<number, Set<number>>(); const indegree = new Map<number, number>(); sccs.forEach((_, i) => { componentEdges.set(i, new Set()); indegree.set(i, 0) })
  for (const edge of edges) { const source = componentOf.get(edge.source); const target = componentOf.get(edge.target); if (source === undefined || target === undefined || source === target || componentEdges.get(source)!.has(target)) continue; componentEdges.get(source)!.add(target); indegree.set(target, indegree.get(target)! + 1) }
  const ranks = new Map<number, number>(); const queue = [...indegree].filter(([, degree]) => degree === 0).map(([id]) => id).sort((a, b) => Math.min(...sccs[a].map((id) => index.get(id)!)) - Math.min(...sccs[b].map((id) => index.get(id)!)))
  queue.forEach((id) => ranks.set(id, 0))
  for (let cursor = 0; cursor < queue.length; cursor++) { const source = queue[cursor]; for (const target of componentEdges.get(source)!) { ranks.set(target, Math.max(ranks.get(target) ?? 0, (ranks.get(source) ?? 0) + 1)); indegree.set(target, indegree.get(target)! - 1); if (indegree.get(target) === 0) queue.push(target) } }
  const rankOf = new Map<string, number>(); for (const [id, component] of sccs.entries()) for (const nodeId of component) rankOf.set(nodeId, ranks.get(id) ?? 0)
  const ranksByNode = new Map<number, GraphNode[]>(); for (const node of nodes) ranksByNode.set(rankOf.get(node.id)!, [...(ranksByNode.get(rankOf.get(node.id)!) ?? []), node])
  const order = new Map<string, number>(); const traversalSeen = new Set<string>(); const visitOrder = (node: GraphNode) => { if (traversalSeen.has(node.id)) return; traversalSeen.add(node.id); order.set(node.id, order.size); for (const edge of sortedEdges(outgoing.get(node.id) ?? [])) { const target = nodes.find((item) => item.id === edge.target); if (target) visitOrder(target) } }; const start = nodes.find((node) => node.data.kind === 'start'); if (start) visitOrder(start); for (const node of nodes) visitOrder(node)
  for (const group of ranksByNode.values()) group.sort((a, b) => (order.get(a.id) ?? Number.MAX_SAFE_INTEGER) - (order.get(b.id) ?? Number.MAX_SAFE_INTEGER) || index.get(a.id)! - index.get(b.id)! || a.id.localeCompare(b.id))
  const position = new Map<string, { x: number; y: number }>(); let componentOffsetY = LAYOUT_ORIGIN_Y
  const undirected = new Map<string, Set<string>>(); for (const node of nodes) undirected.set(node.id, new Set()); for (const edge of edges) { if (ids.has(edge.source) && ids.has(edge.target)) { undirected.get(edge.source)!.add(edge.target); undirected.get(edge.target)!.add(edge.source) } }
  const components: GraphNode[][] = []; const seenNodes = new Set<string>(); for (const node of nodes) { if (seenNodes.has(node.id)) continue; const component: GraphNode[] = []; const pending = [node.id]; seenNodes.add(node.id); while (pending.length) { const id = pending.pop()!; component.push(nodes.find((item) => item.id === id)!); for (const next of undirected.get(id)!) if (!seenNodes.has(next)) { seenNodes.add(next); pending.push(next) } } components.push(component) }
  components.sort((a, b) => (a.some((node) => node.data.kind === 'start') ? -1 : b.some((node) => node.data.kind === 'start') ? 1 : Math.min(...a.map((node) => index.get(node.id)!)) - Math.min(...b.map((node) => index.get(node.id)!))))
  const rankX = new Map<number, number>(); let nextX = LAYOUT_ORIGIN_X
  for (const rank of [...ranksByNode.keys()].sort((a, b) => a - b)) { rankX.set(rank, nextX); nextX += Math.max(...(ranksByNode.get(rank) ?? []).map((node) => nodeDimension(node, dimensions).width), FALLBACK_NODE_WIDTH) + RANK_GAP_X }
  for (const component of components) { const componentIds = new Set(component.map((node) => node.id)); const componentRanks = [...new Set(component.map((node) => rankOf.get(node.id) ?? 0))].sort((a, b) => a - b); let maxY = componentOffsetY
    for (const rank of componentRanks) { const group = (ranksByNode.get(rank) ?? []).filter((node) => componentIds.has(node.id)); if (!group.length) continue; const x = rankX.get(rank) ?? LAYOUT_ORIGIN_X; let y = componentOffsetY; for (const node of group) { position.set(node.id, { x, y }); y += nodeDimension(node, dimensions).height + LANE_GAP_Y } maxY = Math.max(maxY, y) }
    componentOffsetY = maxY + COMPONENT_GAP_Y
  }
  return position
}

type Position = { x: number; y: number }

function positionOf(node: GraphNode, positions: ReadonlyMap<string, Position>): Position {
  return positions.get(node.id) ?? node.position
}

function rectFor(node: GraphNode, position: Position, dimensions: ReadonlyMap<string, NodeDimensions>) {
  const size = nodeDimension(node, dimensions)
  return { ...position, right: position.x + size.width, bottom: position.y + size.height, width: size.width, height: size.height }
}

function visuallyCramped(a: GraphNode, b: GraphNode, positions: ReadonlyMap<string, Position>, dimensions: ReadonlyMap<string, NodeDimensions>): boolean {
  const first = rectFor(a, positionOf(a, positions), dimensions); const second = rectFor(b, positionOf(b, positions), dimensions)
  const horizontalOverlap = first.x < second.right + COLLISION_PADDING_X && first.right + COLLISION_PADDING_X > second.x
  const verticalOverlap = first.y < second.bottom + COLLISION_PADDING_Y && first.bottom + COLLISION_PADDING_Y > second.y
  if (horizontalOverlap && verticalOverlap) return true
  const horizontalGap = Math.max(first.x - second.right, second.x - first.right, 0)
  const verticalGap = Math.max(first.y - second.bottom, second.y - first.bottom, 0)
  return (horizontalGap < HORIZONTAL_GAP && verticalOverlap) || (verticalGap < VERTICAL_GAP && horizontalOverlap)
}

function hasLocalCollision(node: GraphNode, nodes: GraphNode[], dimensions: ReadonlyMap<string, NodeDimensions>): boolean {
  return nodes.some((other) => other.id !== node.id && visuallyCramped(node, other, new Map(), dimensions))
}

function localDirection(nodeId: string, anchorId: string, edges: GraphEdge[], positions: ReadonlyMap<string, Position>): { x: number; y: number } {
  const current = positions.get(nodeId)!; const anchor = positions.get(anchorId)!; const direct = { x: Math.sign(current.x - anchor.x), y: Math.sign(current.y - anchor.y) }
  if (direct.x || direct.y) return direct
  for (const edge of edges) {
    if (edge.target === nodeId && positions.has(edge.source)) {
      const neighbour = positions.get(edge.source)!; const vector = { x: Math.sign(current.x - neighbour.x), y: Math.sign(current.y - neighbour.y) }
      if (vector.x || vector.y) return vector
    }
    if (edge.source === nodeId && positions.has(edge.target)) {
      const neighbour = positions.get(edge.target)!; const vector = { x: Math.sign(current.x - neighbour.x), y: Math.sign(current.y - neighbour.y) }
      if (vector.x || vector.y) return vector
    }
  }
  return { x: 1, y: 0 }
}

function candidatePositions(moving: GraphNode, anchor: GraphNode, direction: { x: number; y: number }, positions: ReadonlyMap<string, Position>, dimensions: ReadonlyMap<string, NodeDimensions>): Position[] {
  const movingRect = rectFor(moving, positionOf(moving, positions), dimensions); const anchorRect = rectFor(anchor, positionOf(anchor, positions), dimensions); const current = positionOf(moving, positions)
  const xRight = anchorRect.right + HORIZONTAL_GAP; const xLeft = anchorRect.x - movingRect.width - HORIZONTAL_GAP
  const yBelow = anchorRect.bottom + VERTICAL_GAP; const yAbove = anchorRect.y - movingRect.height - VERTICAL_GAP
  const horizontal = direction.x >= 0 ? [{ x: xRight, y: current.y }, { x: xLeft, y: current.y }] : [{ x: xLeft, y: current.y }, { x: xRight, y: current.y }]
  const vertical = direction.y >= 0 ? [{ x: current.x, y: yBelow }, { x: current.x, y: yAbove }] : [{ x: current.x, y: yAbove }, { x: current.x, y: yBelow }]
  const diagonal = [
    { x: direction.x >= 0 ? xRight : xLeft, y: direction.y >= 0 ? yBelow : yAbove },
    { x: direction.x >= 0 ? xRight : xLeft, y: direction.y >= 0 ? yAbove : yBelow },
    { x: direction.x >= 0 ? xLeft : xRight, y: direction.y >= 0 ? yBelow : yAbove },
    { x: direction.x >= 0 ? xLeft : xRight, y: direction.y >= 0 ? yAbove : yBelow },
  ]
  return [...(direction.y ? vertical : []), ...(direction.x ? horizontal : []), ...diagonal]
}

function isPositionFree(node: GraphNode, candidate: Position, nodes: GraphNode[], positions: ReadonlyMap<string, Position>, dimensions: ReadonlyMap<string, NodeDimensions>): boolean {
  const next = new Map(positions); next.set(node.id, candidate)
  return nodes.every((other) => other.id === node.id || !visuallyCramped(node, other, next, dimensions))
}

function resolveLocalCollisions(nodes: GraphNode[], edges: GraphEdge[], movableIds: ReadonlySet<string>, dimensions: ReadonlyMap<string, NodeDimensions>, startingPositions?: ReadonlyMap<string, Position>): Map<string, Position> {
  const positions = new Map(nodes.map((node) => [node.id, { ...(startingPositions?.get(node.id) ?? node.position) }]))
  const order = new Map(nodes.map((node, index) => [node.id, index])); const collisions = () => nodes.flatMap((node, index) => nodes.slice(index + 1).filter((other) => visuallyCramped(node, other, positions, dimensions)).map((other) => [node, other] as const))
  for (let pass = 0; pass < MAX_TIDY_PASSES; pass++) {
    const pairs = collisions(); if (!pairs.length) break
    for (const [first, second] of pairs) {
      const firstMovable = movableIds.has(first.id); const secondMovable = movableIds.has(second.id); if (!firstMovable && !secondMovable) continue
      const firstCollisions = pairs.filter(([a, b]) => a.id === first.id || b.id === first.id).length; const secondCollisions = pairs.filter(([a, b]) => a.id === second.id || b.id === second.id).length
      const moving = !firstMovable ? second : !secondMovable ? first : firstCollisions > secondCollisions || (firstCollisions === secondCollisions && (order.get(first.id) ?? 0) < (order.get(second.id) ?? 0)) ? first : second
      const anchor = moving.id === first.id ? second : first; const direction = localDirection(moving.id, anchor.id, edges, positions)
      const candidates = candidatePositions(moving, anchor, direction, positions, dimensions).map((candidate, index) => {
        const anchorPosition = positionOf(anchor, positions)
        const candidateDirection = { x: Math.sign(candidate.x - anchorPosition.x), y: Math.sign(candidate.y - anchorPosition.y) }
        const directionMatches = (direction.x !== 0 && candidateDirection.x === direction.x ? 1 : 0) + (direction.y !== 0 && candidateDirection.y === direction.y ? 1 : 0)
        return { candidate, index, directionMatches, distance: Math.hypot(candidate.x - positions.get(moving.id)!.x, candidate.y - positions.get(moving.id)!.y) }
      }).sort((a, b) => b.directionMatches - a.directionMatches || a.distance - b.distance || a.index - b.index)
      const valid = candidates.find(({ candidate }) => isPositionFree(moving, candidate, nodes, positions, dimensions))
      if (valid) positions.set(moving.id, valid.candidate)
    }
  }
  return positions
}

function applyPositions(nodes: GraphNode[], positions: ReadonlyMap<string, Position>): GraphNode[] {
  let changed = false
  const result = nodes.map((node) => {
    if (node.data.kind === 'comment') return node
    const position = positions.get(node.id) ?? node.position
    if (position.x !== node.position.x || position.y !== node.position.y) changed = true
    return position.x === node.position.x && position.y === node.position.y ? node : { ...node, position }
  })
  return changed ? result : nodes
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
