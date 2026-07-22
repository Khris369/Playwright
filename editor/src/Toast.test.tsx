import { act, fireEvent, render, renderHook, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { ToastViewport, useToasts } from './Toast'

describe('toast notifications', () => {
  it('deduplicates active notifications with the same event key', () => {
    const { result } = renderHook(() => useToasts())

    act(() => {
      result.current.notify('Preview started.', 'info', 'preview:42')
      result.current.notify('Preview started.', 'info', 'preview:42')
    })

    expect(result.current.toasts).toHaveLength(1)
  })

  it('supports keyboard dismissal and standard auto-dismissal', () => {
    vi.useFakeTimers()
    const onDismiss = vi.fn()
    render(<ToastViewport toasts={[{ id: 7, message: 'Saved.', variant: 'success', dedupeKey: 'saved:7' }]} onDismiss={onDismiss}/>)

    const toast = screen.getByRole('status')
    fireEvent.keyDown(toast, { key: 'Escape' })
    expect(onDismiss).toHaveBeenCalledWith(7)

    act(() => vi.advanceTimersByTime(4000))
    expect(onDismiss).toHaveBeenCalledTimes(2)
    vi.useRealTimers()
  })
})
