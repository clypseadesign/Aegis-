import type { ReactNode } from 'react'

/** A labeled form field with accessible labelling and error wiring. */
export function Field({
  label,
  htmlFor,
  error,
  hint,
  children,
}: {
  label: string
  htmlFor: string
  error?: string
  hint?: string
  children: ReactNode
}) {
  return (
    <div className="field">
      <label htmlFor={htmlFor}>{label}</label>
      {children}
      {hint && !error && (
        <p className="field-hint" id={`${htmlFor}-hint`}>
          {hint}
        </p>
      )}
      {error && (
        <p className="field-error" id={`${htmlFor}-error`} role="alert">
          {error}
        </p>
      )}
    </div>
  )
}

/** Inline alert used for API and form errors. */
export function Alert({ kind, children }: { kind: 'error' | 'info' | 'success'; children: ReactNode }) {
  return (
    <div className={`alert alert-${kind}`} role={kind === 'error' ? 'alert' : 'status'}>
      {children}
    </div>
  )
}

/** Full-width message shown while data loads. */
export function Loading({ label = 'Loading…' }: { label?: string }) {
  return (
    <p className="loading" role="status" aria-live="polite">
      {label}
    </p>
  )
}

/** Empty-state message for lists with no records. */
export function EmptyState({ children }: { children: ReactNode }) {
  return <p className="empty-state">{children}</p>
}
