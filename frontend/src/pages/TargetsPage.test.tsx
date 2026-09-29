import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { TargetsPage } from './TargetsPage'

const PROJECT = {
  id: 'p1',
  owner_id: 'u1',
  name: 'Test project',
  description: null,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

function jsonResponse(body: unknown, status = 200) {
  return {
    ok: status < 400,
    status,
    text: async () => JSON.stringify(body),
  } as unknown as Response
}

function makeFetch() {
  return vi.fn(async (input: RequestInfo | URL, _init?: RequestInit) => {
    const url = String(input)
    if (url.endsWith('/api/v1/targets')) {
      return jsonResponse([])
    }
    if (url.endsWith('/api/v1/projects')) {
      return jsonResponse([PROJECT])
    }
    return jsonResponse({}, 404)
  })
}

function renderPage() {
  return render(
    <MemoryRouter>
      <TargetsPage />
    </MemoryRouter>,
  )
}

describe('Target creation authorization attestation', () => {
  let fetchMock: ReturnType<typeof makeFetch>

  beforeEach(() => {
    sessionStorage.clear()
    fetchMock = makeFetch()
    vi.stubGlobal('fetch', fetchMock)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('requires the attestation checkbox before enabling submit', async () => {
    const user = userEvent.setup()
    renderPage()

    const attestation = await screen.findByLabelText(
      /I am authorized to security-test this target/i,
    )
    expect(attestation).toHaveAttribute('type', 'checkbox')
    expect(attestation).not.toBeChecked()

    // Fill the other required fields first, so the only remaining reason the
    // button could be disabled is the missing attestation.
    await user.type(screen.getByLabelText('Name'), 'My model')
    await user.type(screen.getByLabelText('Endpoint'), 'https://api.example.com/v1')
    await user.type(screen.getByLabelText('Model'), 'test-model')

    const submit = screen.getByRole('button', { name: 'Create target' })
    expect(submit).toBeDisabled()

    await user.click(attestation)
    expect(submit).toBeEnabled()
  })

  it('warns about authorized testing only', async () => {
    renderPage()
    expect(
      await screen.findByText(/Only create a target for a system you own/i),
    ).toBeInTheDocument()
  })

  it('explains which provider matches which endpoint', async () => {
    renderPage()
    // Guards against the Groq/Ollama mismatch that produced HTTP 404s.
    expect(
      await screen.findByText(/only a local Ollama server uses 'Ollama'/i),
    ).toBeInTheDocument()
  })

  it('shows a per-provider endpoint example and updates it when the provider changes', async () => {
    const user = userEvent.setup()
    renderPage()

    const endpoint = await screen.findByLabelText('Endpoint')

    // Default provider is openai_compatible.
    expect(endpoint).toHaveAttribute(
      'placeholder',
      'AegisAI adds /chat/completions. e.g. https://api.openrouter.ai/api/v1',
    )
    expect(
      screen.getByText(/AegisAI adds \/chat\/completions/),
    ).toBeInTheDocument()

    // Switching to Ollama must change the guidance to the Ollama path.
    await user.selectOptions(await screen.findByLabelText('Provider'), 'ollama')
    expect(endpoint).toHaveAttribute(
      'placeholder',
      'AegisAI adds /api/chat. e.g. http://host.docker.internal:11434',
    )
    expect(screen.getByText(/AegisAI adds \/api\/chat/)).toBeInTheDocument()
  })

  it('sends authorization_attestation: true when the target is created', async () => {
    const user = userEvent.setup()
    renderPage()

    await user.type(await screen.findByLabelText('Name'), 'My model')
    await user.type(
      screen.getByLabelText('Endpoint'),
      'https://api.groq.com/openai/v1',
    )
    await user.type(screen.getByLabelText('Model'), 'gpt-oss-20b')
    await user.click(
      screen.getByLabelText(/I am authorized to security-test this target/i),
    )
    await user.click(screen.getByRole('button', { name: 'Create target' }))

    await waitFor(() => {
      const post = fetchMock.mock.calls.find(
        ([url, init]) =>
          String(url).endsWith('/api/v1/targets') && init?.method === 'POST',
      )
      expect(post).toBeDefined()
      const body = JSON.parse(post?.[1]?.body as string)
      expect(body.authorization_attestation).toBe(true)
      expect(body.endpoint).toBe('https://api.groq.com/openai/v1')
    })
  })
})
