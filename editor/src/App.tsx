import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  Background, Controls, MiniMap, ReactFlow, applyEdgeChanges, applyNodeChanges,
  reconnectEdge, type Connection, type EdgeChange, type NodeChange, type OnReconnect,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { api, ApiError } from './api'
import { arrange, blankGraph, fromDefinition, linearOrder, rewireOrder, toDefinition, uid } from './graph'
import { Inspector } from './Inspector'
import { Palette } from './Palette'
import { dashboardRunsUrl } from './navigation'
import type { GraphEdge, GraphNode, StepType, ValidationResult, Version } from './types'
import { WorkflowNode } from './WorkflowNode'

type Snapshot = { nodes: GraphNode[]; edges: GraphEdge[] }
const nodeTypes = { workflow: WorkflowNode }

export default function App() {
  const workflowId = Number(new URLSearchParams(location.search).get('workflow_id'))
  const initial = useMemo(blankGraph, [])
  const [nodes, setNodes] = useState(initial.nodes)
  const [edges, setEdges] = useState(initial.edges)
  const [stepTypes, setStepTypes] = useState<StepType[]>([])
  const [versions, setVersions] = useState<Version[]>([])
  const [version, setVersion] = useState<Version>()
  const [selectedId, setSelectedId] = useState<string>()
  const [validation, setValidation] = useState<ValidationResult>({ valid: false, compiled_order: [], errors: [] })
  const [dirty, setDirty] = useState(false)
  const [message, setMessage] = useState('Loading…')
  const [past, setPast] = useState<Snapshot[]>([])
  const [future, setFuture] = useState<Snapshot[]>([])
  const [jsonImport, setJsonImport] = useState('')
  const copied = useRef<GraphNode | undefined>(undefined)
  const reconnectSucceeded = useRef(true)

  const readOnly = Boolean(version?.is_published)
  const canOpenRuns = Boolean(workflowId && version)
  const runsUrl = dashboardRunsUrl(workflowId, version?.id)
  const selected = nodes.find((node) => node.id === selectedId)
  const selectedType = stepTypes.find((step) => step.key === selected?.data.step_type)
  const definition = useMemo(() => toDefinition(nodes, edges), [nodes, edges])
  const definitionKey = JSON.stringify(definition)

  const checkpoint = useCallback(() => {
    setPast((items) => [...items.slice(-99), { nodes, edges }]); setFuture([])
  }, [nodes, edges])
  const commit = useCallback((nextNodes: GraphNode[], nextEdges: GraphEdge[] = edges) => {
    checkpoint(); setNodes(nextNodes); setEdges(nextEdges); setDirty(true)
  }, [checkpoint, edges])

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
        setValidation(result)
        const byNode = result.errors.filter((item) => item.node_id).reduce((map, item) => map.set(item.node_id!, [...(map.get(item.node_id!) ?? []), item]), new Map<string, ValidationResult['errors']>())
        setNodes((current) => current.map((node) => ({ ...node, data: { ...node.data, errors: byNode.get(node.id)?.map((item) => item.message) ?? [] } })))
      }).catch((error) => { if ((error as Error).name !== 'AbortError') setMessage((error as Error).message) }), 250)
    return () => { clearTimeout(timer); controller.abort() }
  }, [definitionKey])

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
  const onConnect = (connection: Connection) => { if (!readOnly) commit(nodes, [...edges, { ...connection, id: uid(), source: connection.source!, target: connection.target! }]) }
  const onReconnect: OnReconnect<GraphEdge> = (oldEdge, connection) => { reconnectSucceeded.current = true; commit(nodes, reconnectEdge(oldEdge, connection, edges)) }

  const addStep = (step: StepType) => {
    const executable = nodes.filter((node) => node.data.kind !== 'comment')
    const node: GraphNode = { id: uid(), type: 'workflow', position: { x: 80 + executable.length * 280, y: 160 }, data: { kind: 'step', step_type: step.key, args: structuredClone(step.default_args), title: step.name } }
    const targets = new Set(edges.map((edge) => edge.target)); const tail = executable.find((item) => !edges.some((edge) => edge.source === item.id) && targets.has(item.id)) ?? executable.at(-1)
    commit([...nodes, node], tail ? [...edges, { id: uid(), source: tail.id, target: node.id }] : edges); setSelectedId(node.id)
  }
  const addComment = () => commit([...nodes, { id: uid(), type: 'workflow', position: { x: 80, y: 360 }, data: { kind: 'comment', text: 'Comment' } }])
  const updateSelected = (data: GraphNode['data']) => { if (!readOnly && selected) commit(nodes.map((node) => node.id === selected.id ? { ...node, data } : node)) }
  const undo = () => { const previous = past.at(-1); if (!previous) return; setFuture((items) => [{ nodes, edges }, ...items]); setPast((items) => items.slice(0, -1)); setNodes(previous.nodes); setEdges(previous.edges); setDirty(true) }
  const redo = () => { const next = future[0]; if (!next) return; setPast((items) => [...items, { nodes, edges }]); setFuture((items) => items.slice(1)); setNodes(next.nodes); setEdges(next.edges); setDirty(true) }
  const duplicate = () => { if (!selected || selected.data.kind === 'start' || readOnly) return; const copy = { ...structuredClone(selected), id: uid(), selected: false, position: { x: selected.position.x + 40, y: selected.position.y + 40 } }; commit([...nodes, copy]); setSelectedId(copy.id) }

  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if (!(event.ctrlKey || event.metaKey)) return
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
    ;[order[index], order[next]] = [order[next], order[index]]; commit(nodes, rewireOrder(order))
  }
  const importDefinition = () => {
    try { const parsed = JSON.parse(jsonImport); const graph = fromDefinition(parsed); checkpoint(); setNodes(graph.nodes.map((node) => ({ ...node, data: { ...node.data, title: stepTypes.find((item) => item.key === node.data.step_type)?.name } }))); setEdges(graph.edges); setDirty(true); setMessage('Imported; validation pending') } catch (error) { setMessage(`Import rejected: ${(error as Error).message}`) }
  }

  return <main className="app-shell">
    <header><a href="/ui">Dashboard</a><h1>Workflow editor</h1><nav className="editor-tabs" aria-label="Editor sections"><span className="editor-tab is-active" aria-current="page">Editor</span><button className="editor-tab" type="button" disabled={!canOpenRuns} title={canOpenRuns ? 'Open the dashboard Runs tab for the current workflow and version.' : 'Load a workflow and version first.'} onClick={() => { window.location.href = runsUrl }}>Runs</button></nav><select value={version?.id ?? ''} onChange={(e) => { const next = versions.find((item) => item.id === Number(e.target.value)); if (next && (!dirty || confirm('Discard unsaved changes?'))) loadVersion(next) }}>{versions.map((item) => <option value={item.id} key={item.id}>v{item.version_number}{item.is_published ? ' · published' : ' · draft'}</option>)}</select><button onClick={createVersion}>New version</button><button onClick={togglePublished} disabled={!version || (!version.is_published && !validation.valid)}>{version?.is_published ? 'Unpublish' : 'Publish'}</button><button onClick={save} disabled={readOnly || !dirty || !validation.valid}>Save</button><span>{message}</span></header>
    <div className="toolbar"><button disabled={!past.length || readOnly} onClick={undo}>Undo</button><button disabled={!future.length || readOnly} onClick={redo}>Redo</button><button disabled={readOnly} onClick={() => commit(arrange(nodes, edges))}>Arrange</button><button disabled={!selected || readOnly} onClick={duplicate}>Duplicate</button><span className={validation.valid ? 'valid' : 'error'}>{validation.valid ? `${validation.compiled_order.length} steps · valid` : `${validation.errors.length} validation errors`}</span></div>
    <div className="workspace"><Palette stepTypes={stepTypes} disabled={readOnly} onAdd={addStep} onComment={addComment}/><section className="canvas"><ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} onNodesChange={onNodesChange} onEdgesChange={onEdgesChange} onConnect={onConnect} onReconnectStart={() => { reconnectSucceeded.current = false }} onReconnect={onReconnect} onReconnectEnd={(_, edge) => { if (!reconnectSucceeded.current) commit(nodes, edges.filter((item) => item.id !== edge.id)) }} onSelectionChange={({ nodes: selectedNodes }) => setSelectedId(selectedNodes[0]?.id)} onNodeDragStart={checkpoint} fitView deleteKeyCode={readOnly ? null : ['Backspace', 'Delete']}><MiniMap/><Controls/><Background/></ReactFlow></section><Inspector node={selected} stepType={selectedType} readOnly={readOnly} onChange={updateSelected}/></div>
    <section className="bottom-panels"><details><summary>Accessible linear editor</summary><ol>{linearOrder(nodes, edges).map((id, index) => { const node = nodes.find((item) => item.id === id)!; return <li key={id}>{node.data.kind === 'start' ? 'Start' : node.data.title ?? node.data.step_type}<button disabled={readOnly || index <= 1} onClick={() => moveLinear(id, -1)}>Move up</button><button disabled={readOnly || index === linearOrder(nodes, edges).length - 1} onClick={() => moveLinear(id, 1)}>Move down</button></li> })}</ol></details>
      <details><summary>Definition JSON preview / validated import</summary><textarea aria-label="Definition JSON" value={jsonImport || JSON.stringify(definition, null, 2)} onChange={(e) => setJsonImport(e.target.value)}/><button disabled={readOnly} onClick={importDefinition}>Import and validate</button></details></section>
  </main>
}
