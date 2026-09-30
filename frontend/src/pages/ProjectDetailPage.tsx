import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router-dom'

import {
  ApiError,
  executionApi,
  findingApi,
  projectApi,
  reportApi,
  targetApi,
  testApi,
} from '../api/client'
import { explainExecutionError } from '../lib/executionErrors'
import type {
  Evidence,
  Execution,
  Finding,
  Project,
  Report,
  SecurityTest,
  Target,
} from '../api/types'
import { Alert, EmptyState, Loading } from '../components/Primitives'

/**
 * Project workspace: run executions, inspect findings and evidence, and
 * generate or download reports.
 */
export function ProjectDetailPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const id = projectId as string

  const [project, setProject] = useState<Project | null>(null)
  const [tests, setTests] = useState<SecurityTest[]>([])
  const [targets, setTargets] = useState<Target[]>([])
  const [executions, setExecutions] = useState<Execution[]>([])
  const [reports, setReports] = useState<Report[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  const [selectedTestId, setSelectedTestId] = useState('')
  const [selectedTargetId, setSelectedTargetId] = useState('')
  const [selectedExecutionId, setSelectedExecutionId] = useState<string | null>(null)
  const [findings, setFindings] = useState<Finding[]>([])
  const [evidenceByFinding, setEvidenceByFinding] = useState<Record<string, Evidence[]>>({})
  const [reportTitle, setReportTitle] = useState('')
  const [reportFormat, setReportFormat] = useState('json')
  const [seeding, setSeeding] = useState(false)

  /**
   * Refresh only the executions. Used by the poll loop so status updates do not
   * blank the page or clobber in-progress form input.
   */
  const refreshExecutions = useCallback(async () => {
    setExecutions(await executionApi.list(id))
  }, [id])

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [projectDetail, testList, targetList, executionList, reportList] =
        await Promise.all([
          projectApi.get(id),
          testApi.list(id),
          targetApi.list(),
          executionApi.list(id),
          reportApi.list(id),
        ])
      setProject(projectDetail)
      setTests(testList)
      const projectTargets = targetList.filter((target) => target.project_id === id)
      setTargets(projectTargets)
      setExecutions(executionList)
      setReports(reportList)
      setSelectedTestId((current) => current || testList[0]?.id || '')
      // Seed the target selection from this project's targets only. Using the
      // unfiltered list here selected another project's target, which the
      // dropdown then could not display and the run silently submitted.
      setSelectedTargetId((current) =>
        projectTargets.some((target) => target.id === current)
          ? current
          : (projectTargets[0]?.id ?? ''),
      )
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not load project.')
    } finally {
      setLoading(false)
    }
  }, [id])

  useEffect(() => {
    void load()
  }, [load])

  // Poll while any execution is still in flight, so status and progress update
  // without a manual refresh. The interval is torn down as soon as everything
  // reaches a terminal state, so an idle page makes no further requests.
  const hasActiveExecutions = executions.some(
    (execution) => execution.status === 'pending' || execution.status === 'running',
  )

  useEffect(() => {
    if (!hasActiveExecutions) return

    let cancelled = false
    const timer = window.setInterval(() => {
      if (cancelled) return
      refreshExecutions().catch(() => {
        // A transient poll failure should not surface as a page-level error;
        // the next tick will retry.
      })
    }, 2000)

    return () => {
      cancelled = true
      window.clearInterval(timer)
    }
  }, [hasActiveExecutions, refreshExecutions])

  async function handleSeedLibrary() {
    setSeeding(true)
    setError(null)
    setNotice(null)
    try {
      const result = await testApi.seed(id)
      const parts = [`${result.created} tests loaded`]
      if (result.skipped > 0) parts.push(`${result.skipped} already present`)
      setNotice(`Attack library ready: ${parts.join(', ')}.`)
      await load()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not load the attack library.')
    } finally {
      setSeeding(false)
    }
  }

  async function handleRun() {
    setError(null)
    setNotice(null)
    try {
      const execution = await executionApi.create(id, {
        test_id: selectedTestId || null,
        target_id: selectedTargetId || null,
      })
      // 202-style: the execution is queued, so poll it into the running state.
      await executionApi.run(id, execution.id)
      setNotice('Execution queued. It will appear below shortly.')
      await load()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not start execution.')
    }
  }

  async function handleCancel(execution: Execution) {
    try {
      await executionApi.cancel(id, execution.id)
      await load()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not cancel execution.')
    }
  }

  async function handleSelectExecution(executionId: string) {
    setSelectedExecutionId(executionId)
    setFindings([])
    setEvidenceByFinding({})
    try {
      const list = await findingApi.listForExecution(id, executionId)
      setFindings(list)
      const entries = await Promise.all(
        list.map(async (finding) => {
          const evidence = await findingApi.listEvidence(id, finding.id)
          return [finding.id, evidence] as const
        }),
      )
      setEvidenceByFinding(Object.fromEntries(entries))
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not load findings.')
    }
  }

  async function handleCreateReport(event: FormEvent) {
    event.preventDefault()
    setError(null)
    setNotice(null)
    try {
      await reportApi.create(id, { title: reportTitle, format: reportFormat })
      setReportTitle('')
      setNotice('Report created. Generate it to produce the artifact.')
      await load()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not create report.')
    }
  }

  async function handleGenerateReport(report: Report) {
    setError(null)
    setNotice(null)
    try {
      const generated = await reportApi.generate(id, report.id)
      setNotice(`Report v${generated.version} generated.`)
      await load()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not generate report.')
    }
  }

  async function handleDownloadReport(report: Report) {
    setError(null)
    try {
      const content = await reportApi.download(id, report.id)
      const mime = report.format === 'json' ? 'application/json' : 'text/markdown'
      const extension = report.format === 'json' ? 'json' : 'md'
      const blob = new Blob([content], { type: mime })
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = `${report.title.replace(/[^a-z0-9-_]+/gi, '-').toLowerCase()}-v${report.version}.${extension}`
      document.body.appendChild(anchor)
      anchor.click()
      document.body.removeChild(anchor)
      URL.revokeObjectURL(url)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not download report.')
    }
  }

  if (loading) return <Loading />
  if (error && !project) return <Alert kind="error">{error}</Alert>
  if (!project) return <EmptyState>Project not found.</EmptyState>

  const projectTargets = targets
  // The run controls stay disabled unless the selected target is confirmed to
  // belong to this project. Backend validation remains authoritative; this only
  // prevents submitting a selection the UI cannot legitimately offer.
  const targetIsProjectScoped = projectTargets.some(
    (target) => target.id === selectedTargetId,
  )

  return (
    <section>
      <p className="breadcrumb">
        <Link to="/projects">Projects</Link> / {project.name}
      </p>
      <h1>{project.name}</h1>
      {project.description && <p className="page-subtitle">{project.description}</p>}

      {error && <Alert kind="error">{error}</Alert>}
      {notice && <Alert kind="success">{notice}</Alert>}

      <div className="card">
        <h2>Security tests</h2>
        {tests.length === 0 ? (
          <div className="seed-panel">
            <p>
              This project has no security tests yet. Load the bundled attack library to get 89
              test cases across prompt injection, jailbreak, privacy leakage, RAG, and agent
              tool-use categories.
            </p>
            <button type="button" onClick={() => void handleSeedLibrary()} disabled={seeding}>
              {seeding ? 'Loading library…' : 'Load attack library'}
            </button>
          </div>
        ) : (
          <p className="card-note">
            {tests.length} {tests.length === 1 ? 'test' : 'tests'} available.
          </p>
        )}
      </div>

      <div className="card">
        <h2>Run a security test</h2>
        {tests.length === 0 ? (
          <EmptyState>Load the attack library above to enable test runs.</EmptyState>
        ) : (
          <div className="inline-form">
            <label htmlFor="run-test">Test</label>
            <select
              id="run-test"
              value={selectedTestId}
              onChange={(e) => setSelectedTestId(e.target.value)}
            >
              {tests.map((test) => (
                <option key={test.id} value={test.id}>
                  {test.name}
                </option>
              ))}
            </select>

            <label htmlFor="run-target">Target</label>
            <select
              id="run-target"
              value={selectedTargetId}
              onChange={(e) => setSelectedTargetId(e.target.value)}
            >
              {projectTargets.length === 0 && <option value="">No targets in project</option>}
              {projectTargets.map((target) => (
                <option key={target.id} value={target.id}>
                  {target.name}
                </option>
              ))}
            </select>

            <button
              type="button"
              onClick={() => void handleRun()}
              disabled={selectedTestId === '' || !targetIsProjectScoped}
            >
              Run test
            </button>
            {!targetIsProjectScoped && (
              <p className="inline-warning" role="status">
                {projectTargets.length === 0
                  ? 'Add a target to this project before running a test.'
                  : 'Select a target that belongs to this project.'}
              </p>
            )}
          </div>
        )}
      </div>

      <div className="card">
        <div className="card-header">
          <h2>Executions</h2>
          {hasActiveExecutions && (
            <span className="live-indicator" role="status" aria-live="polite">
              <span className="live-dot" aria-hidden="true" />
              Updating live
            </span>
          )}
        </div>
        {executions.length === 0 ? (
          <EmptyState>No executions yet.</EmptyState>
        ) : (
          <table className="table">
            <caption className="sr-only">Executions in this project</caption>
            <thead>
              <tr>
                <th scope="col">Started</th>
                <th scope="col">Status</th>
                <th scope="col">Result</th>
                <th scope="col">Reason</th>
                <th scope="col">Actions</th>
              </tr>
            </thead>
            <tbody>
              {executions.map((execution) => {
                const failure = explainExecutionError(execution.error)
                return (
                  <tr key={execution.id}>
                    <td>{execution.started_at ?? execution.created_at}</td>
                    <td>
                      <span className={`badge badge-${execution.status}`}>{execution.status}</span>
                    </td>
                    <td>
                      <span className={`badge badge-${execution.result}`}>{execution.result}</span>
                    </td>
                    <td className="failure-cell">
                      {failure ? (
                        <>
                          <strong>{failure.cause}</strong>
                          <span>{failure.action}</span>
                        </>
                      ) : (
                        <span className="failure-none">—</span>
                      )}
                    </td>
                    <td>
                      <button
                        type="button"
                        onClick={() => void handleSelectExecution(execution.id)}
                      >
                        Findings
                      </button>{' '}
                      {(execution.status === 'pending' || execution.status === 'running') && (
                        <button type="button" onClick={() => void handleCancel(execution)}>
                          Cancel
                        </button>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>

      {selectedExecutionId && (
        <div className="card">
          <h2>Findings</h2>
          {findings.length === 0 ? (
            <EmptyState>No findings recorded for this execution.</EmptyState>
          ) : (
            findings.map((finding) => (
              <article key={finding.id} className="finding">
                <h3>
                  {finding.title}{' '}
                  <span className={`badge badge-severity-${finding.severity}`}>
                    {finding.severity}
                  </span>
                </h3>
                {finding.description && <p>{finding.description}</p>}
                <p className="finding-meta">
                  Status: {finding.status} · Created: {finding.created_at}
                </p>

                <h4>Evidence</h4>
                {(evidenceByFinding[finding.id] ?? []).length === 0 ? (
                  <EmptyState>No evidence attached.</EmptyState>
                ) : (
                  (evidenceByFinding[finding.id] ?? []).map((item) => (
                    <details key={item.id} className="evidence">
                      <summary>
                        {item.kind} — {item.description ?? 'no description'}
                      </summary>
                      <pre>{JSON.stringify(item.content, null, 2)}</pre>
                    </details>
                  ))
                )}
              </article>
            ))
          )}
        </div>
      )}

      <div className="card">
        <h2>Reports</h2>
        <form className="inline-form" onSubmit={(e) => void handleCreateReport(e)}>
          <label htmlFor="report-title">Title</label>
          <input
            id="report-title"
            required
            maxLength={200}
            value={reportTitle}
            onChange={(e) => setReportTitle(e.target.value)}
          />
          <label htmlFor="report-format">Format</label>
          <select
            id="report-format"
            value={reportFormat}
            onChange={(e) => setReportFormat(e.target.value)}
          >
            <option value="json">JSON</option>
            <option value="markdown">Markdown</option>
          </select>
          <button type="submit" disabled={reportTitle.trim() === ''}>
            Create report
          </button>
        </form>

        {reports.length === 0 ? (
          <EmptyState>No reports yet.</EmptyState>
        ) : (
          <table className="table">
            <caption className="sr-only">Reports in this project</caption>
            <thead>
              <tr>
                <th scope="col">Title</th>
                <th scope="col">Format</th>
                <th scope="col">Version</th>
                <th scope="col">Generated</th>
                <th scope="col">Actions</th>
              </tr>
            </thead>
            <tbody>
              {reports.map((report) => (
                <tr key={report.id}>
                  <td>{report.title}</td>
                  <td>{report.format}</td>
                  <td>v{report.version}</td>
                  <td>{report.generated_at ?? 'not generated'}</td>
                  <td>
                    <button type="button" onClick={() => void handleGenerateReport(report)}>
                      Generate
                    </button>{' '}
                    <button
                      type="button"
                      disabled={!report.generated_at}
                      onClick={() => void handleDownloadReport(report)}
                    >
                      Download
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </section>
  )
}
