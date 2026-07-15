import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { Palette } from './Palette'
import { Inspector } from './Inspector'
import type { GraphNode, StepType } from './types'

const step: StepType = { key: 'wait_timeout', name: 'Wait timeout', category: 'Wait', description: 'Bounded wait', default_args: { timeout_ms: 1000 }, args_schema: {}, editor_schema: { fields: [{ path: 'timeout_ms', widget: 'text' }] } }

describe('editor components', () => {
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
})
