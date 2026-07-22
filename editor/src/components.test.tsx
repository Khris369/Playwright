import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { Palette } from './Palette'
import { Inspector } from './Inspector'
import { AgentPairingControl } from './App'
import type { GraphNode, StepType } from './types'

const step: StepType = { key: 'wait_timeout', name: 'Wait timeout', category: 'Wait', description: 'Bounded wait', default_args: { timeout_ms: 1000 }, args_schema: {}, editor_schema: { fields: [{ path: 'timeout_ms', widget: 'text' }] } }

describe('editor components', () => {
  it('opens and closes the global agent status popover', () => {
    render(<AgentPairingControl connected={false} />)
    const trigger = screen.getByRole('button', { name: 'Local picker agent status' })
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    fireEvent.click(trigger)
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('submits pairing from the popover and supports unpairing', async () => {
    window.localStorage.clear()
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => ({ paired: true, expires_at: '2030-01-01T00:00:00Z' }) })
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => ({ unpaired: true, revoked: 1 }) })
    vi.stubGlobal('fetch', fetchMock)
    render(<AgentPairingControl connected={false} />)
    fireEvent.click(screen.getByRole('button', { name: 'Local picker agent status' }))
    fireEvent.change(screen.getByLabelText('Agent pairing code'), { target: { value: 'AB12-CD34' } })
    fireEvent.keyDown(screen.getByLabelText('Agent pairing code'), { key: 'Enter' })
    await waitFor(() => expect(screen.getByText(/Paired to/)).toBeInTheDocument())
    expect(fetchMock).toHaveBeenCalledWith('/editor-picker/pairings/approve', expect.objectContaining({ method: 'POST' }))
    fireEvent.click(screen.getByRole('button', { name: 'Unpair agent' }))
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith('/editor-picker/pairings/device', expect.objectContaining({ method: 'DELETE' })))
    vi.unstubAllGlobals()
  })

  it('searches the palette and creates a node', () => {
    const add = vi.fn(); render(<Palette stepTypes={[step]} disabled={false} onAdd={add} onComment={() => undefined}/>)
    fireEvent.change(screen.getByLabelText('Search nodes'), { target: { value: 'wait' } })
    fireEvent.click(screen.getByText('Wait timeout')); expect(add).toHaveBeenCalledWith(step)
    fireEvent.change(screen.getByLabelText('Search nodes'), { target: { value: 'missing' } })
    expect(screen.queryByText('Wait timeout')).not.toBeInTheDocument()
  })

  it('rejects invalid advanced JSON and applies valid JSON', () => {
    const change = vi.fn(); const node: GraphNode = { id: 'x', type: 'workflow', position: { x: 0, y: 0 }, data: { kind: 'step', step_type: step.key, args: step.default_args } }
    render(<Inspector node={node} stepType={step} readOnly={false} onChange={change}/>)
    fireEvent.change(screen.getByLabelText('Advanced arguments JSON'), { target: { value: '{' } }); fireEvent.click(screen.getByText('Apply JSON'))
    expect(document.querySelector('.error')).toHaveTextContent(/property name|JSON/i)
    fireEvent.change(screen.getByLabelText('Advanced arguments JSON'), { target: { value: '{"timeout_ms":2}' } }); fireEvent.click(screen.getByText('Apply JSON'))
    expect(change).toHaveBeenCalled()
  })

  it('edits locator properties through separate fields', () => {
    const click: StepType = { ...step, key: 'click', name: 'Click', default_args: { target: { strategy: 'label', label: 'Field label', exact: true } }, editor_schema: { fields: [{ path: 'target', widget: 'locator' }] } }
    const node: GraphNode = { id: 'click', type: 'workflow', position: { x: 0, y: 0 }, data: { kind: 'step', step_type: 'click', args: click.default_args } }
    const change = vi.fn(); render(<Inspector node={node} stepType={click} readOnly={false} onChange={change}/>)
    fireEvent.change(screen.getByDisplayValue('Field label'), { target: { value: 'Email address' } })
    expect(change).toHaveBeenCalledWith(expect.objectContaining({ args: { target: expect.objectContaining({ strategy: 'label', label: 'Email address', exact: true }) } }))
  })

  it('removes stale locator fields when changing click locator strategy', () => {
    const click: StepType = {
      ...step,
      key: 'click',
      name: 'Click',
      default_args: { target: { strategy: 'role', role: 'button', name: 'Submit', exact: true } },
      editor_schema: { fields: [{ path: 'target', widget: 'locator' }] },
    }
    const node: GraphNode = { id: 'click', type: 'workflow', position: { x: 0, y: 0 }, data: { kind: 'step', step_type: 'click', args: click.default_args } }
    const change = vi.fn()
    render(<Inspector node={node} stepType={click} readOnly={false} onChange={change}/>)

    fireEvent.change(screen.getByDisplayValue('Role'), { target: { value: 'text' } })

    expect(change).toHaveBeenCalledWith(expect.objectContaining({
      args: {
        target: {
          strategy: 'text',
          text: 'Submit',
          exact: true,
          match: 'strict',
        },
      },
    }))
  })

  it('keeps numeric timeout values as numbers', () => {
    const timeout: StepType = {
      key: 'wait_timeout',
      name: 'Wait timeout',
      category: 'Wait',
      description: 'Bounded wait',
      default_args: { timeout_ms: 1000 },
      args_schema: { properties: { timeout_ms: { type: 'integer' } } },
      editor_schema: { fields: [{ path: 'timeout_ms', widget: 'text' }] },
    }
    const node: GraphNode = { id: 'timeout', type: 'workflow', position: { x: 0, y: 0 }, data: { kind: 'step', step_type: 'wait_timeout', args: { timeout_ms: 1000 } } }
    const change = vi.fn()
    render(<Inspector node={node} stepType={timeout} readOnly={false} onChange={change}/>)
    expect(screen.getByText('Seconds')).toBeInTheDocument()
    const input = screen.getByDisplayValue('1')
    expect(input).toHaveAttribute('type', 'number')
    fireEvent.change(input, { target: { value: '2.5' } })
    expect(change).toHaveBeenCalledWith(expect.objectContaining({ args: { timeout_ms: 2500 } }))
  })

  it('supports a run input for visible text clicks', () => {
    const click: StepType = { ...step, key: 'click', name: 'Click', default_args: { target: { strategy: 'text', text: 'Select an option', exact: true } }, editor_schema: { fields: [{ path: 'target', widget: 'locator' }] } }
    const node: GraphNode = { id: 'dynamic-click', type: 'workflow', position: { x: 0, y: 0 }, data: { kind: 'step', step_type: 'click', args: click.default_args } }
    const change = vi.fn()
    const view = render(<Inspector node={node} stepType={click} readOnly={false} onChange={change} />)

    fireEvent.click(view.getByLabelText('Use run input'))
    expect(change).toHaveBeenLastCalledWith(expect.objectContaining({ args: { target: expect.objectContaining({ strategy: 'text', text: '{{ inputs.target_text }}' }) } }))

    view.rerender(<Inspector node={{ ...node, data: { ...node.data, args: { target: { strategy: 'text', text: '{{ inputs.target_text }}', exact: true } } } }} stepType={click} readOnly={false} onChange={change} />)
    expect(view.getByDisplayValue('Resolved from run input: target_text')).toBeDisabled()
    fireEvent.change(view.getByLabelText('Input name'), { target: { value: 'option_text' } })
    expect(change).toHaveBeenLastCalledWith(expect.objectContaining({ args: { target: expect.objectContaining({ text: '{{ inputs.option_text }}' }) } }))
  })

  it.each([
    ['css', { strategy: 'css', selector: '#password', exact: true }, 'CSS selector'],
    ['label', { strategy: 'label', label: 'Password', exact: true }, 'Label'],
    ['text', { strategy: 'text', text: 'Sign in', exact: true }, 'Visible text'],
  ] as const)('places Pick beside the %s locator field', (_strategy, locator, fieldLabel) => {
    const click: StepType = { ...step, key: 'click', name: 'Click', default_args: { target: locator }, editor_schema: { fields: [{ path: 'target', widget: 'locator' }] } }
    const node: GraphNode = { id: 'picker-layout', type: 'workflow', position: { x: 0, y: 0 }, data: { kind: 'step', step_type: 'click', args: click.default_args } }
    render(<Inspector node={node} stepType={click} readOnly={false} onChange={() => undefined} picker={{ workflowId: 1, clientId: 'xxxxxxxxxxxxxxxx', agentConnected: true, session: { sessionId: 's', status: 'Browser ready', requestedUrl: '' } }} />)
    const expectedValue = 'selector' in locator ? locator.selector : 'label' in locator ? locator.label : locator.text
    const valueInput = screen.getByDisplayValue(expectedValue)
    const field = valueInput.closest('label') as HTMLElement
    expect(within(field).getByRole('button', { name: /Pick target element/ })).toBeEnabled()
    expect(screen.getAllByText(fieldLabel).length).toBeGreaterThan(0)
  })

  it('places Pick beside Role accessible name, not the role control', () => {
    const click: StepType = { ...step, key: 'click', name: 'Click', default_args: { target: { strategy: 'role', role: 'textbox', name: 'Password', exact: true } }, editor_schema: { fields: [{ path: 'target', widget: 'locator' }] } }
    const node: GraphNode = { id: 'role-picker-layout', type: 'workflow', position: { x: 0, y: 0 }, data: { kind: 'step', step_type: 'click', args: click.default_args } }
    render(<Inspector node={node} stepType={click} readOnly={false} onChange={() => undefined} picker={{ workflowId: 1, clientId: 'xxxxxxxxxxxxxxxx', agentConnected: true, session: { sessionId: 's', status: 'Browser ready', requestedUrl: '' } }} />)
    const roleInput = screen.getByDisplayValue('textbox')
    expect(within(roleInput.closest('label') as HTMLElement).queryByRole('button', { name: /Pick target element/ })).not.toBeInTheDocument()
    const nameInput = screen.getByDisplayValue('Password')
    expect(within(nameInput.closest('label') as HTMLElement).getByRole('button', { name: /Pick target element/ })).toBeEnabled()
  })

  it('places Pick beside each Fill ticket fields target and updates that row', async () => {
    const fill: StepType = { ...step, key: 'ticket_fill_fields', name: 'Fill ticket fields', default_args: { fields: [{ target: { strategy: 'label', label: 'Subject', exact: true }, control_type: 'text', value: 'Issue' }] }, editor_schema: { fields: [{ path: 'fields', widget: 'ticket-fields' }] } }
    const node: GraphNode = { id: 'ticket-fields-picker', type: 'workflow', position: { x: 0, y: 0 }, data: { kind: 'step', step_type: fill.key, args: fill.default_args } }
    const change = vi.fn()
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({}) })
    vi.stubGlobal('fetch', fetchMock)
    const view = render(<Inspector node={node} stepType={fill} readOnly={false} onChange={change} picker={{ workflowId: 1, clientId: 'xxxxxxxxxxxxxxxx', agentConnected: true, session: { sessionId: 's', status: 'Browser ready', requestedUrl: '' } }} />)
    fireEvent.click(view.getByRole('button', { name: /Pick target element/ }))
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith('/editor-picker/sessions/s/inspect', expect.objectContaining({ method: 'POST' })))
    view.rerender(<Inspector node={node} stepType={fill} readOnly={false} onChange={change} picker={{ workflowId: 1, clientId: 'xxxxxxxxxxxxxxxx', agentConnected: true, session: { sessionId: 's', status: 'Select an element', requestedUrl: '' }, event: { type: 'picker.element.selected', session_id: 's', payload: { locator: { strategy: 'css', selector: 'input[name="subject"]', exact: true, match: 'strict' }, validation: { match_count: 1, matches_selected_element: true } } } }} />)
    fireEvent.click(view.getByRole('button', { name: 'Accept locator' }))
    await waitFor(() => expect(change).toHaveBeenCalledWith(expect.objectContaining({ args: { fields: [{ target: { strategy: 'css', selector: 'input[name="subject"]', exact: true, match: 'strict' }, control_type: 'text', value: 'Issue' }] } })))
    vi.unstubAllGlobals()
  })

  it('does not render the detached picker section', () => {
    const click: StepType = { ...step, key: 'click', name: 'Click', default_args: { target: { strategy: 'label', label: 'Password', exact: true } }, editor_schema: { fields: [{ path: 'target', widget: 'locator' }] } }
    const node: GraphNode = { id: 'no-detached-picker', type: 'workflow', position: { x: 0, y: 0 }, data: { kind: 'step', step_type: 'click', args: click.default_args } }
    render(<Inspector node={node} stepType={click} readOnly={false} onChange={() => undefined} picker={{ workflowId: 1, clientId: 'xxxxxxxxxxxxxxxx', agentConnected: true, session: { sessionId: 's', status: 'Browser ready', requestedUrl: '' } }} />)
    expect(screen.queryByRole('region', { name: /Element picker/ })).not.toBeInTheDocument()
  })

  it('renders Verify element under Assertion and stores its expected state and timeout', () => {
    const verify: StepType = {
      key: 'verify_element', name: 'Verify element', category: 'Assertion', description: 'Require a target to match an expected state.',
      default_args: { target: { strategy: 'text', text: 'Status', exact: true }, expected_state: 'visible', timeout_ms: 30000 },
      args_schema: { properties: { timeout_ms: { type: 'integer' } } },
      editor_schema: { fields: [
        { path: 'target', widget: 'locator' },
        { path: 'expected_state', widget: 'select', options: [{ value: 'visible', label: 'Visible' }, { value: 'unchecked', label: 'Unchecked' }] },
        { path: 'timeout_ms', widget: 'text' },
      ] },
    }
    const node: GraphNode = { id: 'verify', type: 'workflow', position: { x: 0, y: 0 }, data: { kind: 'step', step_type: verify.key, args: verify.default_args } }
    const change = vi.fn()
    render(<><Palette stepTypes={[verify]} disabled={false} onAdd={() => undefined} onComment={() => undefined} /><Inspector node={node} stepType={verify} readOnly={false} onChange={change} /></>)
    expect(screen.getByRole('heading', { name: 'Assertion' })).toBeInTheDocument()
    expect(screen.getAllByText('Verify element')).toHaveLength(2)
    expect(screen.getByText('Expected state')).toBeInTheDocument()
    expect(screen.getByText('Verify within')).toBeInTheDocument()
    fireEvent.change(screen.getByDisplayValue('Visible'), { target: { value: 'unchecked' } })
    expect(change).toHaveBeenCalledWith(expect.objectContaining({ args: expect.objectContaining({ expected_state: 'unchecked' }) }))
    fireEvent.change(screen.getByDisplayValue('30'), { target: { value: '10' } })
    expect(change).toHaveBeenCalledWith(expect.objectContaining({ args: expect.objectContaining({ timeout_ms: 10000 }) }))
  })

  it('shows picker availability and accepts a locator only into local node state', async () => {
    const click: StepType = { ...step, key: 'click', name: 'Click', default_args: { target: { strategy: 'label', label: 'Field label', exact: true } }, editor_schema: { fields: [{ path: 'target', widget: 'locator' }] } }
    const node: GraphNode = { id: 'click', type: 'workflow', position: { x: 0, y: 0 }, data: { kind: 'step', step_type: 'click', args: click.default_args } }
    const change = vi.fn()
    render(<Inspector node={node} stepType={click} readOnly={false} onChange={change} picker={{ workflowId: 1, clientId: 'xxxxxxxxxxxxxxxx', agentConnected: false }} />)
    expect(screen.getByRole('button', { name: 'Pick target element for target' })).toBeDisabled()

    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({}) })
    vi.stubGlobal('fetch', fetchMock)
    const active = render(<Inspector node={node} stepType={click} readOnly={false} onChange={change} picker={{ workflowId: 1, clientId: 'xxxxxxxxxxxxxxxx', agentConnected: true, session: { sessionId: 's', status: 'Browser ready', requestedUrl: '' } }} />)
    fireEvent.click(within(active.container).getByRole('button', { name: 'Pick target element for target' }))
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith('/editor-picker/sessions/s/inspect', expect.objectContaining({ method: 'POST' })))
    active.rerender(<Inspector node={node} stepType={click} readOnly={false} onChange={change} picker={{ workflowId: 1, clientId: 'xxxxxxxxxxxxxxxx', agentConnected: true, session: { sessionId: 's', status: 'Select an element', requestedUrl: '' }, event: { type: 'picker.element.selected', session_id: 's', payload: { locator: { strategy: 'role', role: 'button', name: 'Submit', exact: false, match: 'nth', nth: 2, scope: { strategy: 'css', selector: '.dialog', exact: true } }, validation: { match_count: 1, matches_selected_element: true } } } }} />)
    fireEvent.click(within(active.container).getByRole('button', { name: 'Accept locator' }))
    await waitFor(() => expect(change).toHaveBeenCalledWith(expect.objectContaining({ args: { target: { strategy: 'role', role: 'button', name: 'Submit', exact: false, match: 'nth', nth: 2, scope: { strategy: 'css', selector: '.dialog', exact: true } } } })))
    // Inspector acceptance has no publish or run action.
    expect(screen.queryByText('Publish')).not.toBeInTheDocument()
    vi.unstubAllGlobals()
  })

  it('explains unavailable picker states and blocks published workflows', () => {
    const click: StepType = { ...step, key: 'click', name: 'Click', default_args: { target: { strategy: 'label', label: 'Password', exact: true } }, editor_schema: { fields: [{ path: 'target', widget: 'locator' }] } }
    const node: GraphNode = { id: 'read-only-picker', type: 'workflow', position: { x: 0, y: 0 }, data: { kind: 'step', step_type: 'click', args: click.default_args } }
    const picker = { workflowId: 1, clientId: 'xxxxxxxxxxxxxxxx', agentConnected: true, session: { sessionId: 's', status: 'Browser ready', requestedUrl: '' } }
    const view = render(<Inspector node={node} stepType={click} readOnly picker={picker} onChange={() => undefined} />)
    const button = screen.getByRole('button', { name: /Pick target element/ })
    expect(button).toBeDisabled()
    expect(button).toHaveAttribute('title', 'Published versions are read-only.')
    view.rerender(<Inspector node={node} stepType={click} readOnly={false} onChange={() => undefined} picker={{ ...picker, session: undefined }} />)
    expect(screen.getByRole('button', { name: /Pick target element/ })).toHaveAttribute('title', 'Open the picker browser first.')
  })

  it('starts a new inspection immediately from Pick Again', async () => {
    const click: StepType = { ...step, key: 'click', name: 'Click', default_args: { target: { strategy: 'label', label: 'Password', exact: true } }, editor_schema: { fields: [{ path: 'target', widget: 'locator' }] } }
    const node: GraphNode = { id: 'pick-again', type: 'workflow', position: { x: 0, y: 0 }, data: { kind: 'step', step_type: 'click', args: click.default_args } }
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({}) })
    vi.stubGlobal('fetch', fetchMock)
    render(<Inspector node={node} stepType={click} readOnly={false} onChange={() => undefined} picker={{ workflowId: 1, clientId: 'xxxxxxxxxxxxxxxx', agentConnected: true, session: { sessionId: 's', status: 'Element selected', requestedUrl: '' }, drafts: { 'pick-again:target': { sessionId: 's', status: 'Element selected', requestedUrl: '', result: { locator: { strategy: 'label', label: 'Password', exact: true }, validation: { match_count: 1, matches_selected_element: true } } } } }} />)
    fireEvent.click(screen.getByRole('button', { name: 'Pick Again' }))
    await waitFor(() => expect(fetchMock).toHaveBeenNthCalledWith(1, '/editor-picker/sessions/s/inspect/cancel', expect.objectContaining({ method: 'POST' })))
    await waitFor(() => expect(fetchMock).toHaveBeenNthCalledWith(2, '/editor-picker/sessions/s/inspect', expect.objectContaining({ method: 'POST' })))
    vi.unstubAllGlobals()
  })

  it('does not apply a picker result to a different selected node', () => {
    const click: StepType = { ...step, key: 'click', name: 'Click', default_args: { target: { strategy: 'label', label: 'Password', exact: true } }, editor_schema: { fields: [{ path: 'target', widget: 'locator' }] } }
    const first: GraphNode = { id: 'first-node', type: 'workflow', position: { x: 0, y: 0 }, data: { kind: 'step', step_type: 'click', args: click.default_args } }
    const second: GraphNode = { id: 'second-node', type: 'workflow', position: { x: 0, y: 0 }, data: { kind: 'step', step_type: 'click', args: click.default_args } }
    const change = vi.fn()
    const picker = { workflowId: 1, clientId: 'xxxxxxxxxxxxxxxx', agentConnected: true, session: { sessionId: 's', status: 'Select an element', requestedUrl: '' }, drafts: { 'first-node:target': { sessionId: 's', status: 'Select an element', requestedUrl: '' } }, event: { type: 'picker.element.selected', session_id: 's', payload: { locator: { strategy: 'role', role: 'textbox', name: 'Password', exact: true }, validation: { match_count: 1, matches_selected_element: true } } } }
    const view = render(<Inspector node={first} stepType={click} readOnly={false} onChange={change} picker={picker} />)
    view.rerender(<Inspector node={second} stepType={click} readOnly={false} onChange={change} picker={picker} />)
    expect(screen.queryByText('Selected element')).not.toBeInTheDocument()
    expect(change).not.toHaveBeenCalled()
  })
})
