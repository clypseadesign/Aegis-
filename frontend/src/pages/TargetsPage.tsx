import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'

import { ApiError, credentialApi, projectApi, targetApi } from '../api/client'
import type { Credential, Project, Target, TargetProvider } from '../api/types'
import { Alert, EmptyState, Field, Loading } from '../components/Primitives'

const PROVIDERS: Array<{ value: TargetProvider; label: string; needsModel: boolean }> = [
  { value: 'openai_compatible', label: 'OpenAI-compatible API', needsModel: true },
  { value: 'ollama', label: 'Ollama', needsModel: true },
  { value: 'custom_rest', label: 'Custom REST endpoint', needsModel: false },
]

/** Redacted placeholder shown wherever a secret value would otherwise appear. */
export const REDACTED = '••••••••'

export function TargetsPage() {
  const [targets, setTargets] = useState<Target[]>([])
  const [projects, setProjects] = useState<Project[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  const [projectId, setProjectId] = useState('')
  const [name, setName] = useState('')
  const [provider, setProvider] = useState<TargetProvider>('openai_compatible')
  const [endpoint, setEndpoint] = useState('')
  const [model, setModel] = useState('')
  const [creating, setCreating] = useState(false)
  const [attested, setAttested] = useState(false)

  const needsModel = PROVIDERS.find((p) => p.value === provider)?.needsModel ?? false

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [targetList, projectList] = await Promise.all([
        targetApi.list(),
        projectApi.list(),
      ])
      setTargets(targetList)
      setProjects(projectList)
      if (projectList.length > 0 && projectId === '') {
        setProjectId(projectList[0].id)
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not load targets.')
    } finally {
      setLoading(false)
    }
    // projectId intentionally omitted: it is only seeded, never a load input.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  async function handleCreate(event: FormEvent) {
    event.preventDefault()
    // The backend requires an explicit affirmative attestation, so refuse to
    // submit without it rather than sending a request it will reject.
    if (!attested) {
      setError(
        'Confirm you are authorized to security-test this target before creating it.',
      )
      return
    }
    setCreating(true)
    setError(null)
    try {
      await targetApi.create({
        project_id: projectId,
        name,
        provider,
        endpoint,
        model: model || null,
        authorization_attestation: true,
      })
      setName('')
      setEndpoint('')
      setModel('')
      setAttested(false)
      setNotice('Target created.')
      await load()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not create target.')
    } finally {
      setCreating(false)
    }
  }

  async function handleDelete(target: Target) {
    const confirmed = window.confirm(`Delete target "${target.name}"?`)
    if (!confirmed) return
    try {
      await targetApi.remove(target.id)
      await load()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not delete target.')
    }
  }

  return (
    <section>
      <h1>Targets</h1>
      <p className="page-subtitle">
        A target is the AI system under test. AegisAI only tests systems you are authorized to
        assess.
      </p>

      {error && <Alert kind="error">{error}</Alert>}
      {notice && <Alert kind="success">{notice}</Alert>}

      {projects.length > 0 && (
        <form className="card create-form" onSubmit={handleCreate}>
          <h2>New target</h2>

          <Field label="Project" htmlFor="target-project">
            <select
              id="target-project"
              name="project"
              required
              value={projectId}
              onChange={(e) => setProjectId(e.target.value)}
            >
              {projects.map((project) => (
                <option key={project.id} value={project.id}>
                  {project.name}
                </option>
              ))}
            </select>
          </Field>

          <Field label="Name" htmlFor="target-name">
            <input
              id="target-name"
              name="name"
              required
              maxLength={200}
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </Field>

          <Field
            label="Provider"
            htmlFor="target-provider"
            hint="Pick the one matching your endpoint. Hosted OpenAI-compatible APIs (OpenAI, Groq, Together, vLLM) use 'OpenAI-compatible API'; only a local Ollama server uses 'Ollama'. A mismatch returns HTTP 404."
          >
            <select
              id="target-provider"
              name="provider"
              value={provider}
              onChange={(e) => setProvider(e.target.value as TargetProvider)}
            >
              {PROVIDERS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </Field>

          <Field
            label="Endpoint"
            htmlFor="target-endpoint"
            hint="Absolute http or https URL. Loopback and private addresses are blocked."
          >
            <input
              id="target-endpoint"
              name="endpoint"
              type="url"
              required
              placeholder="https://api.example.com/v1"
              value={endpoint}
              onChange={(e) => setEndpoint(e.target.value)}
            />
          </Field>

          {needsModel && (
            <Field label="Model" htmlFor="target-model">
              <input
                id="target-model"
                name="model"
                required
                value={model}
                onChange={(e) => setModel(e.target.value)}
              />
            </Field>
          )}

          <p className="attestation-note">
            AegisAI sends adversarial prompts to the target you configure. Only create a target
            for a system you own or have explicit written authorization to test.
          </p>

          <div className="checkbox-field">
            <input
              id="target-attestation"
              name="authorization_attestation"
              type="checkbox"
              required
              checked={attested}
              onChange={(e) => setAttested(e.target.checked)}
            />
            <label htmlFor="target-attestation">
              I am authorized to security-test this target
            </label>
          </div>

          <button
            type="submit"
            disabled={
              creating ||
              projectId === '' ||
              (needsModel && model === '') ||
              !attested
            }
          >
            {creating ? 'Creating…' : 'Create target'}
          </button>
        </form>
      )}

      <h2>Registered targets</h2>
      {loading ? (
        <Loading />
      ) : targets.length === 0 ? (
        <EmptyState>No targets yet. Create one to start testing.</EmptyState>
      ) : (
        <ul className="card-list">
          {targets.map((target) => {
            const project = projects.find((p) => p.id === target.project_id)
            return (
              <li key={target.id} className="card">
                <div className="card-body">
                  <h3>{target.name}</h3>
                  <dl className="meta">
                    <div>
                      <dt>Project</dt>
                      <dd>
                        <Link to={`/projects/${target.project_id}`}>
                          {project?.name ?? target.project_id}
                        </Link>
                      </dd>
                    </div>
                    <div>
                      <dt>Provider</dt>
                      <dd>{target.provider}</dd>
                    </div>
                    <div>
                      <dt>Model</dt>
                      <dd>{target.model ?? '—'}</dd>
                    </div>
                    <div>
                      <dt>Status</dt>
                      <dd>{target.status}</dd>
                    </div>
                  </dl>
                </div>
                <div className="card-actions">
                  <Link to={`/targets/${target.id}`}>Manage</Link>
                  <button type="button" className="danger" onClick={() => void handleDelete(target)}>
                    Delete
                  </button>
                </div>
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}

interface CredentialsPanelProps {
  targetId: string
}

export function CredentialsPanel({ targetId }: CredentialsPanelProps) {
  const [credentials, setCredentials] = useState<Credential[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [credentialType, setCredentialType] = useState('api_key')
  // Held only for the lifetime of the form; cleared on submit and on unmount.
  const [secretValue, setSecretValue] = useState('')
  const [notice, setNotice] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      setCredentials(await credentialApi.list(targetId))
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not load credentials.')
    } finally {
      setLoading(false)
    }
  }, [targetId])

  useEffect(() => {
    void load()
  }, [load])

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    setNotice(null)
    try {
      await credentialApi.create(targetId, {
        credential_type: credentialType,
        value: secretValue,
      })
      // Drop the plaintext immediately; it is never needed again in the UI.
      setSecretValue('')
      setNotice('Credential stored. The value is encrypted and cannot be read back.')
      await load()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not store credential.')
    }
  }

  async function handleRevoke(credential: Credential) {
    try {
      await credentialApi.revoke(targetId, credential.id)
      await load()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not revoke credential.')
    }
  }

  return (
    <div className="card">
      <h2>Credentials</h2>
      <p className="card-note">
        Credentials are encrypted at rest with Fernet. Values are write-only — the API never
        returns a stored secret, so it cannot be displayed here.
      </p>

      {error && <Alert kind="error">{error}</Alert>}
      {notice && <Alert kind="success">{notice}</Alert>}

      <form className="inline-form" onSubmit={handleSubmit}>
        <Field label="Type" htmlFor="cred-type">
          <input
            id="cred-type"
            name="credentialType"
            value={credentialType}
            onChange={(e) => setCredentialType(e.target.value)}
          />
        </Field>
        <Field label="Secret value" htmlFor="cred-value">
          <input
            id="cred-value"
            name="secretValue"
            type="password"
            required
            autoComplete="off"
            spellCheck={false}
            value={secretValue}
            onChange={(e) => setSecretValue(e.target.value)}
          />
        </Field>
        <button type="submit" disabled={secretValue === ''}>
          Store credential
        </button>
      </form>

      <h3>Stored credentials</h3>
      {loading ? (
        <Loading />
      ) : credentials.length === 0 ? (
        <EmptyState>No credentials stored for this target.</EmptyState>
      ) : (
        <table className="table">
          <caption className="sr-only">Stored credentials for this target</caption>
          <thead>
            <tr>
              <th scope="col">Type</th>
              <th scope="col">Value</th>
              <th scope="col">Version</th>
              <th scope="col">State</th>
              <th scope="col">Actions</th>
            </tr>
          </thead>
          <tbody>
            {credentials.map((credential) => (
              <tr key={credential.id}>
                <td>{credential.credential_type}</td>
                <td>
                  <code>{REDACTED}</code>
                </td>
                <td>v{credential.version}</td>
                <td>{credential.revoked ? 'Revoked' : 'Active'}</td>
                <td>
                  {!credential.revoked && (
                    <button type="button" onClick={() => void handleRevoke(credential)}>
                      Revoke
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
