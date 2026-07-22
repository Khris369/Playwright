import { useCallback, useEffect, useRef, useState } from 'react'

export type ToastVariant = 'info' | 'success' | 'warning' | 'error'
export type ToastNotification = { id: number; message: string; variant: ToastVariant; dedupeKey: string }
export type Notify = (message: string, variant?: ToastVariant, dedupeKey?: string) => void

const durationByVariant: Record<ToastVariant, number> = {
  info: 4000,
  success: 4000,
  warning: 6000,
  error: 8000,
}

export function useToasts() {
  const [toasts, setToasts] = useState<ToastNotification[]>([])
  const nextId = useRef(1)
  const notify = useCallback<Notify>((message, variant = 'info', dedupeKey = `${variant}:${message}`) => {
    if (!message) return
    setToasts((current) => current.some((toast) => toast.dedupeKey === dedupeKey)
      ? current
      : [...current, { id: nextId.current++, message, variant, dedupeKey }])
  }, [])
  const dismiss = useCallback((id: number) => setToasts((current) => current.filter((toast) => toast.id !== id)), [])
  return { toasts, notify, dismiss }
}

function ToastItem({ toast, onDismiss }: { toast: ToastNotification; onDismiss: (id: number) => void }) {
  useEffect(() => {
    const timer = window.setTimeout(() => onDismiss(toast.id), durationByVariant[toast.variant])
    return () => window.clearTimeout(timer)
  }, [onDismiss, toast.id, toast.variant])

  return <div className={`toast toast-${toast.variant}`} role={toast.variant === 'error' ? 'alert' : 'status'} onKeyDown={(event) => { if (event.key === 'Escape') onDismiss(toast.id) }}>
    <span>{toast.message}</span>
    <button type="button" aria-label={`Dismiss ${toast.variant} notification`} onClick={() => onDismiss(toast.id)}>×</button>
  </div>
}

export function ToastViewport({ toasts, onDismiss }: { toasts: ToastNotification[]; onDismiss: (id: number) => void }) {
  return <div className="toast-viewport" aria-label="Notifications">
    {toasts.map((toast) => <ToastItem key={toast.id} toast={toast} onDismiss={onDismiss} />)}
  </div>
}
