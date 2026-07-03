import { useMemo, useState } from 'react'
import { api } from './api'
import type { Definition, StepType } from './types'

type AssistantAction = { action: 'add_step'; step_type: string; args: Record<string, unknown> }
type AssistantResponse = { model: string; answer: string; actions: AssistantAction[] }

type Props = {
  workflowId?: number
  versionId?: number
  definition: Definition
  stepTypes: StepType[]
  disabled: boolean
  onApply: (actions: AssistantAction[]) => void
  onClose?: () => void
}

export function AssistantPanel({ workflowId, versionId, definition, stepTypes, disabled, onApply, onClose }: Props) {
  const [question, setQuestion] = useState('')
  const [html, setHtml] = useState('')
  const [response, setResponse] = useState<AssistantResponse>()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const knownTypes = useMemo(() => new Set(stepTypes.map((step) => step.key)), [stepTypes])
  const applicable = response?.actions.filter((action) => knownTypes.has(action.step_type)) ?? []

  const ask = async () => {
    const prompt = question.trim()
    if (!prompt || loading) return
    setLoading(true); setError('')
    try {
      const result = await api<AssistantResponse>('/editor-assistant', {
        method: 'POST',
        body: JSON.stringify({
          question: prompt,
          html_snippet: html.trim() || null,
          workflow_id: workflowId || null,
          workflow_version_id: versionId || null,
          current_definition_json: definition,
        }),
      })
      if (!result || typeof result.answer !== 'string' || !Array.isArray(result.actions)) throw new Error('Assistant returned an invalid response')
      setResponse(result)
    } catch (cause) {
      setError((cause as Error).message)
    } finally {
      setLoading(false)
    }
  }

  return <div className="assistant-panel" role="dialog" aria-label="Editor Assistant">
    <header><strong>Editor Assistant</strong>{onClose && <button type="button" aria-label="Close assistant" onClick={onClose}>×</button>}</header>
    <p>Ask for advice, locator help, or workflow steps. Proposed edits are reviewed before they are added.</p>
    <textarea aria-label="Assistant question" rows={3} maxLength={10_000} placeholder="Add a click step for the Submit button, then wait for Success text." value={question} onChange={(event) => setQuestion(event.target.value)} />
    <details><summary>Optional HTML snippet</summary><textarea aria-label="Relevant HTML" rows={5} maxLength={100_000} value={html} onChange={(event) => setHtml(event.target.value)} /></details>
    <button type="button" disabled={!question.trim() || loading} onClick={ask}>{loading ? 'Thinking…' : 'Ask Assistant'}</button>
    {error && <span className="error">{error}</span>}
    {response && <div className="assistant-response"><p>{response.answer}</p>{response.actions.length > 0 && <><h3>Proposed steps</h3><ol>{response.actions.map((action, index) => <li key={`${action.step_type}-${index}`} className={knownTypes.has(action.step_type) ? '' : 'error'}><strong>{action.step_type}</strong><pre>{JSON.stringify(action.args, null, 2)}</pre>{!knownTypes.has(action.step_type) && <small>Unknown step type; this proposal cannot be applied.</small>}</li>)}</ol><button type="button" disabled={disabled || applicable.length === 0} onClick={() => onApply(applicable)}>Add {applicable.length} proposed step{applicable.length === 1 ? '' : 's'}</button></>}</div>}
  </div>
}
