import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'

import { ApiError, projectApi } from '../api/client'
import type { Project } from '../api/types'
import { Alert, EmptyState, Field, Loading } from '../components/Primitives'

export function ProjectsPage() {
  const [projects, setProjects] = useState<Project[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [creating, setCreating] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      setProjects(await projectApi.list())
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not load projects.')
    } finally {
      setLoading(false)
    }
  }, [])
  useEffect(() => {
    void load()
  }, [load])

  async function handleCreate(event: FormEvent) {
    event.preventDefault()
    setCreating(true)
    setError(null)
    try {
      await projectApi.create({ name, description: description || null })
      setName('')
      setDescription('')
      await load()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not create project.')
    } finally {
      setCreating(false)
    }
  }

  async function handleDelete(project: Project) {
    const confirmed = window.confirm(
      `Delete project "${project.name}"? This also removes its tests, executions, findings and reports.`,
    )
    if (!confirmed) return
    try {
      await projectApi.remove(project.id)
      await load()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not delete project.')
    }
  }

  return (
    <section>
      <h1>Projects</h1>
      <p className="page-subtitle">
        A project groups targets, security tests, executions, findings, and reports.
      </p>

      {error && <Alert kind="error">{error}</Alert>}

      <form className="card create-form" onSubmit={handleCreate}>
        <h2>New project</h2>
        <Field label="Name" htmlFor="project-name">
          <input
            id="project-name"
            name="name"
            required
            maxLength={200}
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </Field>
        <Field label="Description" htmlFor="project-description">
          <textarea
            id="project-description"
            name="description"
            rows={2}
            maxLength={1000}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </Field>
        <button type="submit" disabled={creating || name.trim() === ''}>
          {creating ? 'Creating…' : 'Create project'}
        </button>
      </form>

      <h2>Your projects</h2>
      {loading ? (
        <Loading />
      ) : projects.length === 0 ? (
        <EmptyState>No projects yet. Create one to get started.</EmptyState>
      ) : (
        <ul className="card-list">
          {projects.map((project) => (
            <li key={project.id} className="card">
              <div className="card-body">
                <h3>{project.name}</h3>
                {project.description && <p>{project.description}</p>}
              </div>
              <div className="card-actions">
                <Link to={`/projects/${project.id}`}>Open</Link>
                <button
                  type="button"
                  className="danger"
                  onClick={() => void handleDelete(project)}
                >
                  Delete
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
