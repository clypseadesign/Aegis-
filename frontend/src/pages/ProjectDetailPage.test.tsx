import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ProjectDetailPage } from './ProjectDetailPage'

/**
 * These tests cover the two features added after the first release: the
 * "Load attack library" button and live execution polling.
 */

const PROJECT = {
  id: 'p1',
  owner_id: 'u1',
  name: 'Test project',
  description: null,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

const TARGET = {
  id: 't1',
  project_id: 'p1',
  name: 'Local model',
  description: null,
  provider: 'ollama',
  endpoint: 'http://localhost:11434',
  model: 'llama3',
  capabilities: [],
  timeout_seconds: 30,
  rate_limit_per_minute: 60,
  status: 'active',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

function makeExecution(overrides: Record<string, unknown> = {}) {
  return {
    id: 'e1',
    project_id: 'p1',
    test_id: 'st1',
    target_id: 't1',
    status: 'succeeded',
    result: 'fail',
    started_at: '2026-01-01T00:00:00Z',
    completed_at: '2026-01-01T00:01:00Z',
    created_by: 'u1',
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:01:00Z',
    ...overrides,
  }
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/projects/p1']}>
      <Routes>
        <Route path="/projects/:projectId" element={<ProjectDetailPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

/**
 * Route fetch calls by URL suffix.
 *
 * Matching prefers `endsWith` because `/projects/p1` is a substring of every
 * project-scoped URL, and `/assessments/tests` is a prefix of the seed URL.
 * A longest-first `includes` search gets both wrong.
 */
function router(routes: Record<string, { body: unknown; status?: number }>) {
  const keys = Object.keys(routes)

  const resolve = (url: string) =>
    keys.find((key) => url.endsWith(key)) ?? keys.find((key) => url.includes(key))

  return vi.fn(async (input: RequestInfo | URL) => {
    const url = typeof input === 'string' ? input : input.toString()
    const match = resolve(url)
    if (!match) {
      return {
        ok: false,
        status: 404,
        text: async () => JSON.stringify({ error: { code: 'NOT_FOUND', message: url } }),
      } as unknown as Response
    }
    const route = routes[match]
    return {
      ok: (route.status ?? 200) < 400,
      status: route.status ?? 200,
      text: async () => JSON.stringify(route.body),
    } as unknown as Response
  })
}

const baseRoutes = {
  '/projects/p1': { body: PROJECT },
  '/assessments/tests': { body: [] },
  '/targets': { body: [TARGET] },
  '/assessments/executions': { body: [] },
  '/assessments/reports': { body: [] },
}

describe('Load attack library', () => {
  beforeEach(() => {
    sessionStorage.clear()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('prompts the user when the project has no tests', async () => {
    vi.stubGlobal('fetch', router(baseRoutes))
    renderPage()

    expect(
      await screen.findByRole('button', { name: 'Load attack library' }),
    ).toBeInTheDocument()
    expect(screen.getByText(/no security tests yet/i)).toBeInTheDocument()
  })

  it('calls the seed endpoint and reports the result', async () => {
    const user = userEvent.setup()
    let seeded = false

    const fetchMock = router({
      ...baseRoutes,
      '/tests/seed': { body: { created: 89, skipped: 0, invalid: 0, total: 89 } },
      '/assessments/tests': {
        get body() {
          return seeded
            ? [
                {
                  id: 'st1',
                  project_id: 'p1',
                  name: 'Direct instruction override',
                  description: null,
                  provider: 'openai_compatible',
                  required_capabilities: [],
                  config: { category: 'prompt_injection', grading: {} },
                  created_at: '2026-01-01T00:00:00Z',
                  updated_at: '2026-01-01T00:00:00Z',
                },
              ]
            : []
        },
      },
    })

    const original = fetchMock.getMockImplementation()!
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        if (typeof input === 'string' && input.includes('/tests/seed')) seeded = true
        return original(input)
      }) as unknown as typeof fetch,
    )

    renderPage()

    await user.click(await screen.findByRole('button', { name: 'Load attack library' }))

    await waitFor(() => {
      expect(screen.getByText(/89 tests loaded/i)).toBeInTheDocument()
    })
    // The run panel becomes available once tests exist.
    expect(await screen.findByLabelText('Test')).toBeInTheDocument()
  })

  it('surfaces a seed failure without clearing the page', async () => {
    const user = userEvent.setup()
    vi.stubGlobal(
      'fetch',
      router({
        ...baseRoutes,
        '/tests/seed': {
          status: 500,
          body: { error: { code: 'INTERNAL', message: 'Seeding blew up.' } },
        },
      }),
    )

    renderPage()
    await user.click(await screen.findByRole('button', { name: 'Load attack library' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Seeding blew up.')
    // The button remains so the user can retry.
    expect(screen.getByRole('button', { name: 'Load attack library' })).toBeInTheDocument()
  })

  it('hides the prompt and shows the test count once seeded', async () => {
    vi.stubGlobal(
      'fetch',
      router({
        ...baseRoutes,
        '/assessments/tests': {
          body: [
            {
              id: 'st1',
              project_id: 'p1',
              name: 'Direct instruction override',
              description: null,
              provider: 'openai_compatible',
              required_capabilities: [],
              config: { category: 'prompt_injection', grading: {} },
              created_at: '2026-01-01T00:00:00Z',
              updated_at: '2026-01-01T00:00:00Z',
            },
          ],
        },
      }),
    )

    renderPage()

    expect(await screen.findByText(/1 test available/i)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Load attack library' })).not.toBeInTheDocument()
  })
})

describe('Execution polling', () => {
  beforeEach(() => {
    sessionStorage.clear()
    vi.useFakeTimers({ shouldAdvanceTime: true })
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it('polls while an execution is in flight and stops once terminal', async () => {
    let calls = 0
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      calls += 1

      if (url.includes('/assessments/executions') && !url.includes('/run')) {
        // First poll still running, later polls terminal.
        const terminal = calls > 6
        return {
          ok: true,
          status: 200,
          text: async () =>
            JSON.stringify([makeExecution({ status: terminal ? 'succeeded' : 'running' })]),
        } as unknown as Response
      }

      const match =
        Object.keys(baseRoutes).find((key) => url.endsWith(key)) ??
        Object.keys(baseRoutes).find((key) => url.includes(key))
      if (!match) {
        return {
          ok: false,
          status: 404,
          text: async () => '{}',
        } as unknown as Response
      }
      return {
        ok: true,
        status: 200,
        text: async () => JSON.stringify(baseRoutes[match as keyof typeof baseRoutes].body),
      } as unknown as Response
    })

    vi.stubGlobal('fetch', fetchMock)
    renderPage()

    await waitFor(() => {
      expect(screen.getByText('Updating live')).toBeInTheDocument()
    })

    const beforeIdle = calls
    await vi.advanceTimersByTimeAsync(6000)
    expect(calls).toBeGreaterThan(beforeIdle)

    await waitFor(
      () => {
        expect(screen.queryByText('Updating live')).not.toBeInTheDocument()
      },
      { timeout: 8000 },
    )
  })

  it('does not poll when every execution is already terminal', async () => {
    const fetchMock = router({
      ...baseRoutes,
      '/assessments/executions': { body: [makeExecution()] },
    })

    vi.stubGlobal('fetch', fetchMock)
    renderPage()

    await waitFor(() => {
      expect(screen.getByText('succeeded')).toBeInTheDocument()
    })
    expect(screen.queryByText('Updating live')).not.toBeInTheDocument()

    const afterLoad = (fetchMock as unknown as ReturnType<typeof vi.fn>).mock.calls.length
    await vi.advanceTimersByTimeAsync(8000)
    const after = (fetchMock as unknown as ReturnType<typeof vi.fn>).mock.calls.length
    expect(after).toBe(afterLoad)
  })
})
