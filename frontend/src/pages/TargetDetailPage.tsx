import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { ApiError, targetApi } from '../api/client'
import type { Target } from '../api/types'
import { Alert, Loading } from '../components/Primitives'
import { CredentialsPanel } from './TargetsPage'

export function TargetDetailPage() {
  const { targetId } = useParams<{ targetId: string }>()
  const [target, setTarget] = useState<Target | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!targetId) return
    let cancelled = false

    async function load() {
      setLoading(true)
      setError(null)
      try {
        const loaded = await targetApi.get(targetId as string)
        if (!cancelled) setTarget(loaded)
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : 'Could not load target.')
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    void load()
    return () => {
      cancelled = true
    }
  }, [targetId])

  if (loading) return <Loading />
  if (error) return <Alert kind="error">{error}</Alert>
  if (!target) return <Alert kind="error">Target not found.</Alert>

  return (
    <section>
      <p className="breadcrumb">
        <Link to="/targets">Targets</Link> / {target.name}
      </p>
      <h1>{target.name}</h1>

      <div className="card">
        <h2>Configuration</h2>
        <dl className="meta">
          <div>
            <dt>Provider</dt>
            <dd>{target.provider}</dd>
          </div>
          <div>
            <dt>Endpoint</dt>
            <dd>
              <code>{target.endpoint}</code>
            </dd>
          </div>
          <div>
            <dt>Model</dt>
            <dd>{target.model ?? '—'}</dd>
          </div>
          <div>
            <dt>Capabilities</dt>
            <dd>{target.capabilities.length > 0 ? target.capabilities.join(', ') : '—'}</dd>
          </div>
          <div>
            <dt>Timeout</dt>
            <dd>{target.timeout_seconds}s</dd>
          </div>
          <div>
            <dt>Status</dt>
            <dd>{target.status}</dd>
          </div>
        </dl>
        <p>
          <Link to={`/projects/${target.project_id}`}>Go to project →</Link>
        </p>
      </div>

      <CredentialsPanel targetId={target.id} />
    </section>
  )
}
