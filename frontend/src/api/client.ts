/**
 * Typed API client for the AegisAI backend.
 *
 * Security notes (see `docs/adr/ADR-002-frontend-framework.md`):
 * - The frontend is an untrusted client. It never enforces authorization;
 *   the backend is always the authority.
 * - Access tokens are held in `sessionStorage`, not `localStorage`, so they
 *   do not persist across browser restarts. They are never logged and never
 *   placed in a URL.
 * - There is deliberately no method here that reads a credential's plaintext
 *   value. The backend exposes `POST .../credentials/{id}/resolve`, which
 *   returns the secret, and the UI must never call it.
 */

import type {
  Credential,
  CredentialCreate,
  Evidence,
  Execution,
  ExecutionCreate,
  Finding,
  Project,
  ProjectCreate,
  ProjectUpdate,
  Report,
  ReportComparison,
  ReportCreate,
  SecurityTest,
  SecurityTestCreate,
  Target,
  TargetCreate,
  TargetUpdate,
  TestSeedResult,
  TokenResponse,
  User,
  UUID,
  APIErrorResponse,
} from './types'

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '/api/v1'

const TOKEN_STORAGE_KEY = 'aegis.access_token'
const TOKEN_EXPIRY_KEY = 'aegis.access_token_expires_at'

/** Error raised for any non-2xx API response. */
export class ApiError extends Error {
  readonly status: number
  readonly code: string

  constructor(status: number, code: string, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
  }

  /** True when the request failed because the token is missing or expired. */
  get isUnauthorized(): boolean {
    return this.status === 401
  }
}

/* -------------------------------------------------------------------------- */
/* Token storage                                                              */
/* -------------------------------------------------------------------------- */

export const tokenStore = {
  get(): string | null {
    try {
      return sessionStorage.getItem(TOKEN_STORAGE_KEY)
    } catch {
      // sessionStorage can throw in privacy modes; degrade to no token.
      return null
    }
  },

  getExpiresAt(): number | null {
    try {
      const raw = sessionStorage.getItem(TOKEN_EXPIRY_KEY)
      return raw ? Number(raw) : null
    } catch {
      return null
    }
  },

  set(accessToken: string, expiresInSeconds: number): void {
    try {
      sessionStorage.setItem(TOKEN_STORAGE_KEY, accessToken)
      sessionStorage.setItem(
        TOKEN_EXPIRY_KEY,
        String(Date.now() + expiresInSeconds * 1000),
      )
    } catch {
      // Storage unavailable: the in-request header still works for this load.
    }
  },

  clear(): void {
    try {
      sessionStorage.removeItem(TOKEN_STORAGE_KEY)
      sessionStorage.removeItem(TOKEN_EXPIRY_KEY)
    } catch {
      // Nothing to do.
    }
  },

  /** Return the token only if it has not passed its expiry time. */
  getValid(): string | null {
    const token = tokenStore.get()
    if (!token) return null
    const expiresAt = tokenStore.getExpiresAt()
    if (expiresAt !== null && Date.now() >= expiresAt) {
      tokenStore.clear()
      return null
    }
    return token
  },
}

/* -------------------------------------------------------------------------- */
/* Core request helper                                                        */
/* -------------------------------------------------------------------------- */

type UnauthorizedHandler = () => void
let onUnauthorized: UnauthorizedHandler = () => {}

/** Register a callback invoked when the API rejects the current token. */
export function setUnauthorizedHandler(handler: UnauthorizedHandler): void {
  onUnauthorized = handler
}

async function request<T>(
  path: string,
  options: {
    method?: string
    body?: unknown
    auth?: boolean
  } = {},
): Promise<T> {
  const { method = 'GET', body, auth = true } = options

  const headers: Record<string, string> = {}
  if (body !== undefined) {
    headers['Content-Type'] = 'application/json'
  }
  if (auth) {
    const token = tokenStore.getValid()
    if (token) {
      headers['Authorization'] = `Bearer ${token}`
    }
  }

  const response = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  })

  if (response.status === 204) {
    return undefined as T
  }

  const text = await response.text()
  let payload: unknown = undefined
  if (text) {
    try {
      payload = JSON.parse(text)
    } catch {
      payload = undefined
    }
  }

  if (!response.ok) {
    const envelope = payload as APIErrorResponse | undefined
    const code = envelope?.error?.code ?? 'UNKNOWN_ERROR'
    const message =
      envelope?.error?.message ??
      `Request failed with status ${response.status}`
    if (response.status === 401) {
      onUnauthorized()
    }
    throw new ApiError(response.status, code, message)
  }

  return payload as T
}

/* -------------------------------------------------------------------------- */
/* Auth                                                                       */
/* -------------------------------------------------------------------------- */

export const authApi = {
  async register(email: string, password: string): Promise<User> {
    return request<User>('/auth/register', {
      method: 'POST',
      body: { email, password },
      auth: false,
    })
  },

  async login(email: string, password: string): Promise<TokenResponse> {
    const tokens = await request<TokenResponse>('/auth/login', {
      method: 'POST',
      body: { email, password },
      auth: false,
    })
    tokenStore.set(tokens.access_token, tokens.expires_in)
    return tokens
  },

  async me(): Promise<User> {
    return request<User>('/auth/me')
  },

  /**
   * Revoke this account's access tokens server-side, then clear local state.
   *
   * Clearing the token alone would only hide it in this browser; the token
   * itself would stay valid until it expired.
   */
  async logout(): Promise<void> {
    try {
      await request<void>('/auth/logout', { method: 'POST' })
    } catch {
      // A failed revocation must not trap the user in a signed-in-looking UI.
      // The token is cleared regardless; it expires on its own otherwise.
    } finally {
      tokenStore.clear()
    }
  },

  logoutEverywhere(): Promise<void> {
    return request<void>('/auth/logout-all', { method: 'POST' }).finally(() =>
      tokenStore.clear(),
    )
  },
}

/* -------------------------------------------------------------------------- */
/* Projects                                                                   */
/* -------------------------------------------------------------------------- */

export const projectApi = {
  list: () => request<Project[]>('/projects'),
  create: (payload: ProjectCreate) =>
    request<Project>('/projects', { method: 'POST', body: payload }),
  get: (id: UUID) => request<Project>(`/projects/${id}`),
  update: (id: UUID, payload: ProjectUpdate) =>
    request<Project>(`/projects/${id}`, { method: 'PATCH', body: payload }),
  remove: (id: UUID) => request<void>(`/projects/${id}`, { method: 'DELETE' }),
}

/* -------------------------------------------------------------------------- */
/* Targets                                                                    */
/* -------------------------------------------------------------------------- */

export const targetApi = {
  list: () => request<Target[]>('/targets'),
  create: (payload: TargetCreate) =>
    request<Target>('/targets', { method: 'POST', body: payload }),
  get: (id: UUID) => request<Target>(`/targets/${id}`),
  update: (id: UUID, payload: TargetUpdate) =>
    request<Target>(`/targets/${id}`, { method: 'PATCH', body: payload }),
  remove: (id: UUID) => request<void>(`/targets/${id}`, { method: 'DELETE' }),
}

/* -------------------------------------------------------------------------- */
/* Credentials                                                                */
/* -------------------------------------------------------------------------- */

/**
 * Credential management.
 *
 * Note the absence of a `resolve` method. The backend can return a
 * credential's plaintext to an authorized caller, but the UI must never ask
 * for it — showing a stored secret back to a browser widens exposure for no
 * product benefit.
 */
export const credentialApi = {
  list: (targetId: UUID) =>
    request<Credential[]>(`/targets/${targetId}/credentials`),
  create: (targetId: UUID, payload: CredentialCreate) =>
    request<Credential>(`/targets/${targetId}/credentials`, {
      method: 'POST',
      body: payload,
    }),
  revoke: (targetId: UUID, credentialId: UUID) =>
    request<Credential>(`/targets/${targetId}/credentials/${credentialId}/revoke`, {
      method: 'POST',
    }),
  rotate: (targetId: UUID, credentialId: UUID, payload: CredentialCreate) =>
    request<Credential>(`/targets/${targetId}/credentials/${credentialId}/rotate`, {
      method: 'POST',
      body: payload,
    }),
  remove: (targetId: UUID, credentialId: UUID) =>
    request<void>(`/targets/${targetId}/credentials/${credentialId}`, {
      method: 'DELETE',
    }),
}

/* -------------------------------------------------------------------------- */
/* Assessments: tests, executions, findings, evidence, reports                 */
/* -------------------------------------------------------------------------- */

const assessments = (projectId: UUID) => `/projects/${projectId}/assessments`

export const testApi = {
  list: (projectId: UUID) =>
    request<SecurityTest[]>(`${assessments(projectId)}/tests`),
  create: (projectId: UUID, payload: SecurityTestCreate) =>
    request<SecurityTest>(`${assessments(projectId)}/tests`, {
      method: 'POST',
      body: payload,
    }),
  /** Load the bundled attack library into a project. Idempotent. */
  seed: (projectId: UUID, categories: string[] = []) =>
    request<TestSeedResult>(`${assessments(projectId)}/tests/seed`, {
      method: 'POST',
      body: { category: categories },
    }),
  remove: (projectId: UUID, testId: UUID) =>
    request<void>(`${assessments(projectId)}/tests/${testId}`, {
      method: 'DELETE',
    }),
}

export const executionApi = {
  list: (projectId: UUID) =>
    request<Execution[]>(`${assessments(projectId)}/executions`),
  create: (projectId: UUID, payload: ExecutionCreate) =>
    request<Execution>(`${assessments(projectId)}/executions`, {
      method: 'POST',
      body: payload,
    }),
  get: (projectId: UUID, executionId: UUID) =>
    request<Execution>(`${assessments(projectId)}/executions/${executionId}`),
  run: (projectId: UUID, executionId: UUID) =>
    request<Execution>(`${assessments(projectId)}/executions/${executionId}/run`, {
      method: 'POST',
    }),
  cancel: (projectId: UUID, executionId: UUID) =>
    request<Execution>(`${assessments(projectId)}/executions/${executionId}/cancel`, {
      method: 'POST',
    }),
}

export const findingApi = {
  listForExecution: (projectId: UUID, executionId: UUID) =>
    request<Finding[]>(`${assessments(projectId)}/executions/${executionId}/findings`),
  listEvidence: (projectId: UUID, findingId: UUID) =>
    request<Evidence[]>(`${assessments(projectId)}/findings/${findingId}/evidence`),
}

export const reportApi = {
  list: (projectId: UUID) =>
    request<Report[]>(`${assessments(projectId)}/reports`),
  create: (projectId: UUID, payload: ReportCreate) =>
    request<Report>(`${assessments(projectId)}/reports`, {
      method: 'POST',
      body: payload,
    }),
  generate: (projectId: UUID, reportId: UUID) =>
    request<Report>(`${assessments(projectId)}/reports/${reportId}/generate`, {
      method: 'POST',
    }),
  compare: (projectId: UUID, reportAId: UUID, reportBId: UUID) =>
    request<ReportComparison>(
      `${assessments(projectId)}/reports/${reportAId}/compare/${reportBId}`,
    ),
  downloadUrl: (projectId: UUID, reportId: UUID): string =>
    `${API_BASE}${assessments(projectId)}/reports/${reportId}/download`,
  /** Fetch a generated report artifact as text (JSON or Markdown). */
  download: async (projectId: UUID, reportId: UUID): Promise<string> => {
    const token = tokenStore.getValid()
    const response = await fetch(
      reportApi.downloadUrl(projectId, reportId),
      token ? { headers: { Authorization: `Bearer ${token}` } } : {},
    )
    if (!response.ok) {
      throw new ApiError(response.status, 'DOWNLOAD_FAILED', 'Could not download report.')
    }
    return response.text()
  },
}

/* -------------------------------------------------------------------------- */
/* System                                                                     */
/* -------------------------------------------------------------------------- */

export const systemApi = {
  readiness: () => request<Record<string, unknown>>('/system/ready', { auth: false }),
}

export const API_BASE_URL = API_BASE
