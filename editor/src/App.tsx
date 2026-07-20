import { useCallback, useEffect, useMemo, useRef, useState, type MouseEvent } from 'react'
import {
  Background, Controls, MiniMap, ReactFlow, applyEdgeChanges, applyNodeChanges,
  reconnectEdge, type Connection, type EdgeChange, type NodeChange, type OnReconnect, type ReactFlowInstance,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { api, ApiError } from './api'
import { arrange, blankGraph, fromDefinition, isValidConnection, linearOrder, removeNode, rewireOrder, resolveHandleSide, toDefinition, uid } from './graph'
import { spawnNodePosition } from './spawn'
import { Inspector, type PickerDraft } from './Inspector'
import { Palette } from './Palette'
import { dashboardRunsUrl } from './navigation'
import type { GraphEdge, GraphNode, StepType, ValidationResult, Version } from './types'
import { WorkflowNode } from './WorkflowNode'
import { AssistantPanel } from './AssistantPanel'

type Snapshot = { nodes: GraphNode[]; edges: GraphEdge[] }
const nodeTypes = { workflow: WorkflowNode }

function isTextEditingTarget(target: EventTarget | null) {
  if (!(target instanceof HTMLElement)) return false
  return target.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName)
}

type PickerAgentInfo = { last_seen?: string; agent_version?: string; platform?: string; machine?: string; agent_id?: string }

export function AgentPairingControl({ connected, info }: { connected: boolean; info?: PickerAgentInfo }) {
  const [open, setOpen] = useState(false)
  const [code, setCode] = useState('')
  const [message, setMessage] = useState('')
  const [pairedCode, setPairedCode] = useState(() => window.localStorage.getItem('workflow-picker-paired-code') ?? '')
  const [pairedExpiry, setPairedExpiry] = useState(() => window.localStorage.getItem('workflow-picker-paired-expiry') ?? '')
  const [submitting, setSubmitting] = useState(false)
  const root = useRef<HTMLDivElement | null>(null)
  const state = submitting ? 'Pairing' : message && !connected ? 'Failed' : connected ? (pairedCode ? 'Paired' : 'Connected') : 'Unavailable'
  const label = submitting ? 'Pairing…' : connected ? (pairedCode ? `Agent connected · Paired to ${pairedCode}` : 'Agent connected') : 'Agent unavailable'
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => { if (event.key === 'Escape') setOpen(false) }
    const onPointer = (event: PointerEvent) => { if (open && root.current && !root.current.contains(event.target as Node)) setOpen(false) }
    document.addEventListener('keydown', onKey)
    document.addEventListener('pointerdown', onPointer)
    return () => { document.removeEventListener('keydown', onKey); document.removeEventListener('pointerdown', onPointer) }
  }, [open])
  const pair = async () => {
    if (submitting || code.trim().length < 6) return
    setSubmitting(true); setMessage('')
    try {
      const response = await api<{ paired: boolean; expires_at?: string }>('/editor-picker/pairings/approve', { method: 'POST', body: JSON.stringify({ code: code.trim().toUpperCase() }) })
      const normalized = code.trim().toUpperCase()
      setPairedCode(normalized); window.localStorage.setItem('workflow-picker-paired-code', normalized)
      if (response.expires_at) { setPairedExpiry(response.expires_at); window.localStorage.setItem('workflow-picker-paired-expiry', response.expires_at) }
      setCode('')
      setMessage('Pairing approved; waiting for agent')
    } catch (error) { setMessage((error as Error).message) } finally { setSubmitting(false) }
  }
  const unpair = async () => {
    setSubmitting(true); setMessage('')
    try { await api('/editor-picker/pairings/device', { method: 'DELETE' }); setPairedCode(''); setPairedExpiry(''); window.localStorage.removeItem('workflow-picker-paired-code'); window.localStorage.removeItem('workflow-picker-paired-expiry'); setMessage('Agent unpaired') }
    catch (error) { setMessage((error as Error).message) } finally { setSubmitting(false) }
  }
  return <div className="agent-status-control" ref={root}>
    <button type="button" className="agent-status-trigger" aria-haspopup="dialog" aria-expanded={open} aria-label="Local picker agent status" onClick={() => setOpen((value) => !value)}><span className={`agent-status-dot ${connected ? 'is-connected' : 'is-unavailable'}`} aria-hidden="true"/><span className="agent-status-label">{label}</span><span className="agent-status-chevron" aria-hidden="true">⌄</span></button>
    {open && <div className="agent-status-popover" role="dialog" aria-label="Picker agent details">
      <div className="agent-status-heading"><strong>Local picker agent</strong><span className={connected ? 'valid' : 'error'}>{state}</span></div>
      <dl className="agent-details">
        {info?.last_seen && <><dt>Last seen</dt><dd>{new Date(info.last_seen).toLocaleString()}</dd></>}
        {info?.agent_id && <><dt>Agent ID</dt><dd title={info.agent_id}>{info.agent_id}</dd></>}
        {info?.machine && <><dt>Machine</dt><dd>{info.machine}</dd></>}
        {info?.agent_version && <><dt>Version</dt><dd>{info.agent_version}</dd></>}
        {info?.platform && <><dt>Platform</dt><dd>{info.platform}</dd></>}
      </dl>
      {!pairedCode ? <><label className="agent-pairing-field">Pairing code<input aria-label="Agent pairing code" autoFocus value={code} placeholder="AB12-CD34" disabled={submitting} onChange={(event) => setCode(event.target.value.toUpperCase().replace(/[^A-Z0-9-]/g, ''))} onKeyDown={(event) => { if (event.key === 'Enter') { event.preventDefault(); void pair() } }} /></label><button type="button" disabled={submitting || code.length < 6} onClick={() => void pair()}>{submitting ? 'Pairing…' : 'Pair agent'}</button><small>Enter the code printed by the local picker agent.</small></> : <><p className="agent-paired-summary">Paired to <code>{pairedCode}</code>{pairedExpiry && <small>Expires {new Date(pairedExpiry).toLocaleString()}</small>}</p><button type="button" className="agent-unpair" disabled={submitting} onClick={() => void unpair()}>Unpair agent</button><button type="button" disabled={submitting} onClick={() => { setPairedCode(''); setPairedExpiry(''); setMessage('') }}>Pair different agent</button></>}
      {message && <span className="error agent-status-error" role="alert">{message}</span>}
    </div>}
  </div>
}

export default function App() {
  const workflowId = Number(new URLSearchParams(location.search).get('workflow_id'))
  const initial = useMemo(blankGraph, [])
  const [nodes, setNodes] = useState(initial.nodes)
  const [edges, setEdges] = useState(initial.edges)
  const [stepTypes, setStepTypes] = useState<StepType[]>([])
  const [canRun, setCanRun] = useState(false)
  const [versions, setVersions] = useState<Version[]>([])
  const [version, setVersion] = useState<Version>()
  const [selectedId, setSelectedId] = useState<string>()
  const [validation, setValidation] = useState<ValidationResult>({ valid: false, compiled_order: [], errors: [] })
  const [dirty, setDirty] = useState(false)
  const [message, setMessage] = useState('Loading…')
  const [past, setPast] = useState<Snapshot[]>([])
  const [future, setFuture] = useState<Snapshot[]>([])
  const [jsonImport, setJsonImport] = useState('')
  const [assistantOpen, setAssistantOpen] = useState(false)
  const [jsonOpen, setJsonOpen] = useState(false)
  const [sequenceOpen, setSequenceOpen] = useState(true)
  const [contextMenu, setContextMenu] = useState<{ kind: 'node'; nodeId: string; x: number; y: number } | { kind: 'edge'; edgeId: string; x: number; y: number } | null>(null)
  const copied = useRef<GraphNode | undefined>(undefined)
  const reconnectSucceeded = useRef(true)
  const reactFlowWrapper = useRef<HTMLElement | null>(null)
  const reactFlowInstance = useRef<any>(null)
  const pickerClientId = useRef(crypto.randomUUID()).current
  const [pickerAgentConnected, setPickerAgentConnected] = useState(false)
  const [pickerAgentInfo, setPickerAgentInfo] = useState<PickerAgentInfo>()
  const [pickerEvent, setPickerEvent] = useState<{ type: string; session_id?: string; payload?: Record<string, unknown> }>()
  // Picker drafts are keyed by node and locator field so unfinished selections
  // survive switching between nodes without changing workflow arguments.
  const [pickerDrafts, setPickerDrafts] = useState<Record<string, PickerDraft>>({})

  const readOnly = Boolean(version?.is_published)
  const canOpenRuns = Boolean(workflowId && version && canRun)
  const runsUrl = dashboardRunsUrl(workflowId, version?.id)
  const selected = nodes.find((node) => node.id === selectedId)
  const selectedType = stepTypes.find((step) => step.key === selected?.data.step_type)
  const contextNode = contextMenu?.kind === 'node' ? nodes.find((node) => node.id === contextMenu.nodeId) : undefined
  const contextEdge = contextMenu?.kind === 'edge' ? edges.find((edge) => edge.id === contextMenu.edgeId) : undefined
  const definition = useMemo(() => toDefinition(nodes, edges), [nodes, edges])
  const renderedNodes = useMemo(() => nodes.map((node) => ({
    ...node,
    data: {
      ...node.data,
      sequenceSelected: node.id === selectedId,
      source_handle: resolveHandleSide(nodes, edges, node, 'source'),
      target_handle: resolveHandleSide(nodes, edges, node, 'target'),
    },
  })), [nodes, edges, selectedId])
  const renderedEdges = useMemo(() => edges.map((edge) => {
    const sourceNode = nodes.find((node) => node.id === edge.source)
    const targetNode = nodes.find((node) => node.id === edge.target)
    return {
      ...edge,
      sourceHandle: edge.data?.branch ?? (sourceNode ? `source-${resolveHandleSide(nodes, edges, sourceNode, 'source') ?? 'right'}` : undefined),
      targetHandle: targetNode ? `target-${resolveHandleSide(nodes, edges, targetNode, 'target') ?? 'left'}` : undefined,
    }
  }), [nodes, edges])
  const definitionKey = JSON.stringify(definition)
  const sequenceNodes = useMemo(() => {
    const ordered = linearOrder(nodes, edges)
    const seen = new Set(ordered)
    return [...ordered, ...nodes.filter((node) => node.data.kind !== 'comment' && !seen.has(node.id)).map((node) => node.id)]
      .map((id) => nodes.find((node) => node.id === id))
      .filter((node): node is GraphNode => Boolean(node))
  }, [nodes, edges])
  // Node coordinates do not affect execution. Excluding them prevents a validation
  // request (and abort race) for every frame while a node is being dragged.
  const validationKey = JSON.stringify({
    nodes: definition.graph.nodes.map(({ position: _position, ...node }) => node),
    edges: definition.graph.edges,
  })

  useEffect(() => {
    api<{ roles?: string[]; permissions?: string[] }>('/auth/me')
      .then((user) => setCanRun(Boolean(user.permissions?.includes('workflow.run') || user.roles?.includes('admin'))))
      .catch(() => setCanRun(false))
  }, [])

  useEffect(() => {
    let socket: WebSocket | undefined
    let retry: number | undefined
    let stopped = false
    const connect = () => {
      const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
      socket = new WebSocket(`${protocol}//${location.host}/editor-picker/editor`)
      socket.onopen = () => socket?.send(JSON.stringify({ version: 1, type: 'editor.connect', payload: { client_id: pickerClientId } }))
      socket.onmessage = (message) => {
        try {
          const event = JSON.parse(message.data) as { type: string; session_id?: string; payload?: Record<string, unknown> }
          if (event.type === 'editor.connected') { setPickerAgentConnected(Boolean(event.payload?.agent_connected)); setPickerAgentInfo(event.payload as PickerAgentInfo) }
          else setPickerEvent(event)
        } catch { /* Ignore invalid broker messages. */ }
      }
      socket.onclose = () => { if (!stopped) retry = window.setTimeout(connect, 2000) }
    }
    connect()
    const refresh = window.setInterval(() => api<{ connected: boolean } & PickerAgentInfo>('/editor-picker/agent-status').then((status) => { setPickerAgentConnected(status.connected); setPickerAgentInfo(status) }).catch(() => { setPickerAgentConnected(false); setPickerAgentInfo(undefined) }), 10000)
    return () => { stopped = true; socket?.close(); if (retry) clearTimeout(retry); clearInterval(refresh) }
  }, [pickerClientId])

  const checkpoint = useCallback(() => {
    setPast((items) => [...items.slice(-99), { nodes, edges }]); setFuture([])
  }, [nodes, edges])
  const commit = useCallback((nextNodes: GraphNode[], nextEdges: GraphEdge[] = edges) => {
    checkpoint(); setNodes(nextNodes); setEdges(nextEdges); setDirty(true)
  }, [checkpoint, edges])

  const closeContextMenu = useCallback(() => setContextMenu(null), [])

  const deleteEdge = useCallback((edgeId: string) => {
    if (readOnly) return
    if (!edges.some((edge) => edge.id === edgeId)) return
    commit(nodes, edges.filter((edge) => edge.id !== edgeId))
    closeContextMenu()
  }, [closeContextMenu, commit, edges, nodes, readOnly])

  const getCanvasCenter = useCallback(() => {
    const bounds = reactFlowWrapper.current?.getBoundingClientRect()
    const instance = reactFlowInstance.current
    if (!bounds || !instance) return { x: 320, y: 240 }
    return instance.screenToFlowPosition({ x: bounds.width / 2, y: bounds.height / 2 })
  }, [])

  const deleteNode = useCallback((nodeId: string) => {
    if (readOnly) return
    const next = removeNode(nodes, edges, nodeId)
    if (next.nodes === nodes && next.edges === edges) return
    commit(next.nodes, next.edges)
    if (selectedId === nodeId) setSelectedId(undefined)
    closeContextMenu()
  }, [closeContextMenu, commit, edges, nodes, readOnly, selectedId])

  useEffect(() => {
    if (!workflowId) { setMessage('Open this editor with ?workflow_id=<id>.'); return }
    Promise.all([api<StepType[]>('/step-types'), api<Version[]>(`/workflows/${workflowId}/versions`)]).then(async ([types, existing]) => {
      setStepTypes(types)
      let list = existing
      if (!list.length) {
        const graph = blankGraph()
        const created = await api<Version>(`/workflows/${workflowId}/versions`, { method: 'POST', body: JSON.stringify({ definition_json: toDefinition(graph.nodes, graph.edges) }) })
        list = [created]
      }
      setVersions(list); loadVersion(list[0], types); setMessage('Ready')
    }).catch((error) => setMessage((error as Error).message))
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workflowId])

  const loadVersion = (next: Version, types = stepTypes) => {
    const graph = fromDefinition(next.definition_json)
    graph.nodes = graph.nodes.map((node) => ({ ...node, data: { ...node.data, title: types.find((item) => item.key === node.data.step_type)?.name } }))
    setNodes(graph.nodes); setEdges(graph.edges); setVersion(next); setSelectedId(undefined)
    setPast([]); setFuture([]); setDirty(false); setJsonImport(JSON.stringify(next.definition_json, null, 2))
  }

  useEffect(() => {
    const controller = new AbortController()
    const timer = setTimeout(() => api<ValidationResult>('/workflow-definitions/validate', { method: 'POST', body: JSON.stringify({ definition_json: definition }), signal: controller.signal })
      .then((result) => {
        if (!result || typeof result.valid !== 'boolean' || !Array.isArray(result.errors) || !Array.isArray(result.compiled_order)) {
          throw new Error('Validation service returned an invalid response')
        }
        setValidation(result)
        const byNode = result.errors.filter((item) => item.node_id).reduce((map, item) => map.set(item.node_id!, [...(map.get(item.node_id!) ?? []), item]), new Map<string, ValidationResult['errors']>())
        setNodes((current) => current.map((node) => ({ ...node, data: { ...node.data, errors: byNode.get(node.id)?.map((item) => item.message) ?? [] } })))
      }).catch((error) => { if ((error as Error).name !== 'AbortError') setMessage((error as Error).message) }), 250)
    return () => { clearTimeout(timer); controller.abort() }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [validationKey])

  useEffect(() => {
    setJsonImport(JSON.stringify(definition, null, 2))
  }, [definitionKey])

  useEffect(() => {
    if (!version) return
    api<Array<{ id: number }>>(`/workflow-runs?workflow_version_id=${version.id}&limit=1`).then(async (runs) => {
      if (!runs[0]) return
      const statuses = await api<Array<{ step_id?: string; status: string }>>(`/workflow-runs/${runs[0].id}/steps`)
      const map = new Map(statuses.map((item) => [item.step_id, item.status]))
      setNodes((current) => current.map((node) => ({ ...node, data: { ...node.data, runState: map.get(node.id) } })))
    }).catch(() => undefined)
  }, [version?.id])

  useEffect(() => {
    const beforeUnload = (event: BeforeUnloadEvent) => { if (dirty) event.preventDefault() }
    window.addEventListener('beforeunload', beforeUnload); return () => window.removeEventListener('beforeunload', beforeUnload)
  }, [dirty])

  const onNodesChange = (changes: NodeChange<GraphNode>[]) => {
    if (readOnly) return
    if (changes.some((change) => change.type === 'remove')) checkpoint()
    setNodes((current) => applyNodeChanges(changes.filter((change) => change.type !== 'remove' || current.find((node) => node.id === change.id)?.data.kind !== 'start'), current))
    if (changes.some((change) => change.type !== 'select' && change.type !== 'dimensions')) setDirty(true)
  }
  const onEdgesChange = (changes: EdgeChange<GraphEdge>[]) => { if (!readOnly) { if (changes.some((c) => c.type === 'remove')) checkpoint(); setEdges((current) => applyEdgeChanges(changes, current)); setDirty(true) } }
  const onConnect = (connection: Connection) => { if (!readOnly && isValidConnection(connection)) commit(nodes, [...edges, { id: uid(), source: connection.source!, target: connection.target!, data: connection.sourceHandle && ['true', 'false', 'body', 'done'].includes(connection.sourceHandle) ? { branch: connection.sourceHandle as any } : undefined }]) }
  const onReconnect: OnReconnect<GraphEdge> = (oldEdge, connection) => { if (!isValidConnection(connection)) { reconnectSucceeded.current = true; return }; reconnectSucceeded.current = true; commit(nodes, reconnectEdge(oldEdge, connection, edges)) }

  const onNodeContextMenu = (event: MouseEvent, node: GraphNode) => {
    event.preventDefault()
    if (readOnly) return
    setSelectedId(node.id)
    setContextMenu({ kind: 'node', nodeId: node.id, x: event.clientX, y: event.clientY })
  }

  const onEdgeContextMenu = (event: MouseEvent, edge: GraphEdge) => {
    event.preventDefault()
    if (readOnly) return
    setContextMenu({ kind: 'edge', edgeId: edge.id, x: event.clientX, y: event.clientY })
  }

  const addStep = (step: StepType) => {
    const executable = nodes.filter((node) => node.data.kind !== 'comment')
    const node: GraphNode = { id: uid(), type: 'workflow', position: spawnNodePosition(nodes, getCanvasCenter()), data: { kind: 'step', step_type: step.key, args: structuredClone(step.default_args), title: step.name } }
    const targets = new Set(edges.map((edge) => edge.target)); const tail = executable.find((item) => !edges.some((edge) => edge.source === item.id) && targets.has(item.id)) ?? executable.at(-1)
    commit([...nodes, node], tail ? [...edges, { id: uid(), source: tail.id, target: node.id }] : edges); setSelectedId(node.id)
  }
  const addComment = () => commit([...nodes, { id: uid(), type: 'workflow', position: { x: 80, y: 360 }, data: { kind: 'comment', text: 'Comment' } }])
  const addControl = (kind: 'if' | 'loop') => {
    const args = kind === 'if' ? { state_key: 'current_url', operator: 'equals', value: '' } : { state_key: '', operator: 'truthy', value: '', max_iterations: 10 }
    const node: GraphNode = { id: uid(), type: 'workflow', position: spawnNodePosition(nodes, getCanvasCenter()), data: { kind, title: kind === 'if' ? 'If' : 'Loop', args } }
    commit([...nodes, node]); setSelectedId(node.id)
  }
  const applyAssistantSteps = (actions: Array<{ action: 'add_step'; step_type: string; args: Record<string, unknown> }>) => {
    if (readOnly || actions.length === 0) return
    const known = new Map(stepTypes.map((step) => [step.key, step]))
    const nextNodes = [...nodes]
    const nextEdges = [...edges]
    let tail = nextNodes.filter((node) => node.data.kind !== 'comment').find((node) => !nextEdges.some((edge) => edge.source === node.id))
    for (const action of actions.slice(0, 25)) {
      const step = known.get(action.step_type)
      if (!step) continue
      const node: GraphNode = { id: uid(), type: 'workflow', position: spawnNodePosition(nextNodes, getCanvasCenter()), data: { kind: 'step', step_type: step.key, args: structuredClone(action.args), title: step.name } }
      nextNodes.push(node)
      if (tail) nextEdges.push({ id: uid(), source: tail.id, target: node.id })
      tail = node
    }
    commit(nextNodes, nextEdges)
    if (tail) setSelectedId(tail.id)
  }
  const updateSelected = (data: GraphNode['data']) => { if (!readOnly && selected) commit(nodes.map((node) => node.id === selected.id ? { ...node, data } : node)) }
  const undo = () => { const previous = past.at(-1); if (!previous) return; setFuture((items) => [{ nodes, edges }, ...items]); setPast((items) => items.slice(0, -1)); setNodes(previous.nodes); setEdges(previous.edges); setDirty(true) }
  const redo = () => { const next = future[0]; if (!next) return; setPast((items) => [...items, { nodes, edges }]); setFuture((items) => items.slice(1)); setNodes(next.nodes); setEdges(next.edges); setDirty(true) }
  const duplicate = () => { if (!selected || selected.data.kind === 'start' || readOnly) return; const copy = { ...structuredClone(selected), id: uid(), selected: false, position: { x: selected.position.x + 40, y: selected.position.y + 40 } }; commit([...nodes, copy]); setSelectedId(copy.id) }

  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if (!(event.ctrlKey || event.metaKey)) return
      if (isTextEditingTarget(event.target)) return
      if (event.key === 'z') { event.preventDefault(); event.shiftKey ? redo() : undo() }
      if (event.key === 'y') { event.preventDefault(); redo() }
      if (event.key === 'c' && selected) copied.current = structuredClone(selected)
      if (event.key === 'v' && copied.current && !readOnly) { event.preventDefault(); const copy = { ...structuredClone(copied.current), id: uid(), position: { x: copied.current.position.x + 40, y: copied.current.position.y + 40 } }; commit([...nodes, copy]); setSelectedId(copy.id) }
      if (event.key === 'd') { event.preventDefault(); duplicate() }
    }
    window.addEventListener('keydown', handler); return () => window.removeEventListener('keydown', handler)
  })

  const save = async () => {
    if (!version || !validation.valid) return
    try {
      const updated = await api<Version>(`/workflows/versions/${version.id}`, { method: 'PUT', body: JSON.stringify({ definition_json: definition, expected_lock_version: version.lock_version }) })
      setVersion(updated); setVersions((items) => items.map((item) => item.id === updated.id ? updated : item)); setDirty(false); setMessage('Saved')
    } catch (error) {
      if (error instanceof ApiError && error.status === 409) setMessage(`Save conflict: ${JSON.stringify(error.detail)}`)
      else setMessage((error as Error).message)
    }
  }
  const togglePublished = async () => {
    if (!version) return
    const action = version.is_published ? 'unpublish' : 'publish'
    const updated = await api<Version>(`/workflows/versions/${version.id}/${action}`, { method: 'POST', body: JSON.stringify({ expected_lock_version: version.lock_version }) })
    setVersion(updated); setVersions((items) => items.map((item) => item.id === updated.id ? updated : item)); setDirty(false); setMessage(updated.is_published ? 'Published' : 'Unpublished; editing enabled')
  }
  const createVersion = async () => { if (!version) return; const created = await api<Version>(`/workflows/${workflowId}/versions`, { method: 'POST', body: JSON.stringify({ base_version_id: version.id }) }); setVersions((items) => [created, ...items]); loadVersion(created); setMessage('Draft version created') }

  const moveLinear = (id: string, delta: number) => {
    const order = linearOrder(nodes, edges); const index = order.indexOf(id); const next = index + delta
    if (index <= 0 || next <= 0 || next >= order.length) return
    ;[order[index], order[next]] = [order[next], order[index]]
    const nextEdges = rewireOrder(order)
    commit(arrange(nodes, nextEdges), nextEdges)
  }
  const importDefinition = () => {
    try { const parsed = JSON.parse(jsonImport); const graph = fromDefinition(parsed); checkpoint(); setNodes(graph.nodes.map((node) => ({ ...node, data: { ...node.data, title: stepTypes.find((item) => item.key === node.data.step_type)?.name } }))); setEdges(graph.edges); setDirty(true); setMessage('Imported; validation pending') } catch (error) { setMessage(`Import rejected: ${(error as Error).message}`) }
  }

  return <main className="app-shell">
    <header><a href="/ui">Dashboard</a><h1>Workflow editor</h1><nav className="editor-tabs" aria-label="Editor sections"><span className="editor-tab is-active" aria-current="page">Editor</span><button className="editor-tab" type="button" hidden={!canRun} disabled={!canOpenRuns} title={canOpenRuns ? 'Open the dashboard Runs tab for the current workflow and version.' : 'Load a workflow and version first.'} onClick={() => { window.location.href = runsUrl }}>Runs</button></nav><button type="button" aria-expanded={assistantOpen} onClick={() => setAssistantOpen((open) => !open)}>Assistant</button><select value={version?.id ?? ''} onChange={(e) => { const next = versions.find((item) => item.id === Number(e.target.value)); if (next && (!dirty || confirm('Discard unsaved changes?'))) loadVersion(next) }}>{versions.map((item) => <option value={item.id} key={item.id}>v{item.version_number}{item.is_published ? ' · published' : ' · draft'}</option>)}</select><button onClick={createVersion}>New version</button><button onClick={togglePublished} disabled={!version || (!version.is_published && !validation.valid)}>{version?.is_published ? 'Unpublish' : 'Publish'}</button><button onClick={save} disabled={readOnly || !dirty || !validation.valid}>Save</button><span>{message}</span></header>
    {assistantOpen && <div className="assistant-drawer"><AssistantPanel workflowId={workflowId || undefined} versionId={version?.id} definition={definition} stepTypes={stepTypes} disabled={readOnly} onApply={applyAssistantSteps} onClose={() => setAssistantOpen(false)} /></div>}
    <div className="toolbar"><button disabled={!past.length || readOnly} onClick={undo}>Undo</button><button disabled={!future.length || readOnly} onClick={redo}>Redo</button><button disabled={readOnly} onClick={() => commit(arrange(nodes, edges))}>Arrange</button><button disabled={!selected || readOnly} onClick={duplicate}>Duplicate</button><span className={validation.valid ? 'valid' : 'error'}>{validation.valid ? `${validation.compiled_order.length} steps · valid` : `${validation.errors.length} validation errors`}</span><AgentPairingControl connected={pickerAgentConnected} info={pickerAgentInfo}/></div>
    <div className="workspace">
      <Palette stepTypes={stepTypes} disabled={readOnly} onAdd={addStep} onControl={addControl} onComment={addComment}/>
      <section className="canvas" ref={reactFlowWrapper}>
        <aside className={`sequence-rail nodrag nowheel ${sequenceOpen ? '' : 'is-collapsed'}`} aria-label="Workflow sequence"><div className="sequence-rail-header"><h2>Sequence</h2><button type="button" aria-label={sequenceOpen ? 'Collapse sequence' : 'Expand sequence'} aria-expanded={sequenceOpen} onClick={() => setSequenceOpen((open) => !open)}>{sequenceOpen ? '−' : '+'}</button></div>{sequenceOpen && <ol>{sequenceNodes.map((node, index) => <li key={node.id} className={selectedId === node.id ? 'is-selected' : ''}><button type="button" title={`Focus ${node.data.title ?? node.data.step_type ?? node.data.kind}`} onClick={() => { setSelectedId(node.id); reactFlowInstance.current?.fitView({ nodes: [{ id: node.id }], padding: 1.5, duration: 250, maxZoom: 1.2 }) }}><span>{index + 1}</span><small>{node.data.kind === 'start' ? 'Start' : node.data.title ?? node.data.step_type ?? node.data.kind}</small></button>{index > 0 && <div><button aria-label={`Move ${index + 1} up`} disabled={readOnly || index <= 1} onClick={() => moveLinear(node.id, -1)}>↑</button><button aria-label={`Move ${index + 1} down`} disabled={readOnly || index === sequenceNodes.length - 1} onClick={() => moveLinear(node.id, 1)}>↓</button></div>}</li>)}</ol>}</aside>
        <ReactFlow
          nodes={renderedNodes}
          edges={renderedEdges}
          nodeTypes={nodeTypes}
          onInit={(instance) => { reactFlowInstance.current = instance }}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          isValidConnection={isValidConnection}
          onReconnectStart={() => { reconnectSucceeded.current = false }}
          onReconnect={onReconnect}
          onReconnectEnd={(_, edge) => { if (!reconnectSucceeded.current) commit(nodes, edges.filter((item) => item.id !== edge.id)) }}
          onEdgeContextMenu={onEdgeContextMenu}
          onSelectionChange={({ nodes: selectedNodes }) => setSelectedId(selectedNodes[0]?.id)}
          onNodeDragStart={checkpoint}
          onNodeContextMenu={onNodeContextMenu}
          onPaneClick={closeContextMenu}
          onPaneContextMenu={(event) => { event.preventDefault(); closeContextMenu() }}
          connectionRadius={48}
          connectionDragThreshold={1}
          nodeDragThreshold={0}
          autoPanOnConnect
          autoPanOnNodeDrag
          connectOnClick
          defaultEdgeOptions={{ interactionWidth: 24 }}
          fitView
          deleteKeyCode={readOnly ? null : ['Backspace', 'Delete']}
        >
          <MiniMap/>
          <Controls/>
          <Background/>
        </ReactFlow>
{contextMenu && (
          <div className="node-context-menu" style={{ left: contextMenu.x, top: contextMenu.y }}>
            {contextMenu.kind === 'node' ? (
              <button type="button" disabled={readOnly || contextNode?.data.kind === 'start'} onClick={() => deleteNode(contextMenu.nodeId)}>Delete node</button>
            ) : (
              <button type="button" disabled={readOnly || !contextEdge} onClick={() => deleteEdge(contextMenu.edgeId)}>Delete connection</button>
            )}
            <button type="button" onClick={closeContextMenu}>Cancel</button>
          </div>
        )}
      </section>
      <Inspector node={selected} stepType={selectedType} readOnly={readOnly} onChange={updateSelected} picker={workflowId ? { workflowId, clientId: pickerClientId, agentConnected: pickerAgentConnected, event: pickerEvent, drafts: pickerDrafts, onDraftChange: (key, draft) => setPickerDrafts((current) => ({ ...current, [key]: draft })) } : undefined}/>
    </div>
    <section className={`bottom-panels ${jsonOpen ? 'is-expanded' : ''}`}><details open={jsonOpen} onToggle={(event) => setJsonOpen(event.currentTarget.open)}><summary>Definition JSON preview / validated import</summary><div className="json-panel-content"><textarea aria-label="Definition JSON" value={jsonImport || JSON.stringify(definition, null, 2)} onChange={(e) => setJsonImport(e.target.value)}/><button disabled={readOnly} onClick={importDefinition}>Import and validate</button></div></details></section>
  </main>
}
