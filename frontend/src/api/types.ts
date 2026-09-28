/**
 * TypeScript types mirroring the AegisAI backend API contracts.
 *
 * These are hand-maintained to match the Pydantic schemas in
 * `backend/app/schemas/`. The backend is authoritative; if a contract
 * changes there, it must be updated here.
 */

export type UUID = string

export type UserRole = 'super_admin' | 'admin' | 'user' | 'viewer'

export type TargetProvider = 'openai_compatible' | 'ollama' | 'custom_rest'
export type TargetStatus = 'active' | 'inactive'

export type ExecutionStatus =
  | 'pending'
  | 'running'
  | 'succeeded'
  | 'failed'
  | 'cancelled'

export type ExecutionResult = 'pass' | 'fail' | 'inconclusive' | 'no_findings'

export type FindingSeverity = 'info' | 'low' | 'medium' | 'high' | 'critical'
export type FindingStatus = 'open' | 'in_progress' | 'fixed' | 'wont_fix'

export interface APIError {
  code: string
  message: string
}

export interface APIErrorResponse {
  error: APIError
}

export interface User {
  id: UUID
  email: string
  role: UserRole
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
  expires_in: number
}

export interface Project {
  id: UUID
  owner_id: UUID | null
  name: string
  description: string | null
  created_at: string
  updated_at: string
}

export interface ProjectCreate {
  name: string
  description?: string | null
}

export interface ProjectUpdate {
  name?: string
  description?: string | null
}

export interface Target {
  id: UUID
  project_id: UUID
  name: string
  description: string | null
  provider: TargetProvider
  endpoint: string
  model: string | null
  capabilities: string[]
  timeout_seconds: number
  rate_limit_per_minute: number
  status: TargetStatus
  created_at: string
  updated_at: string
}

export interface TargetCreate {
  project_id: UUID
  name: string
  description?: string | null
  provider: TargetProvider
  endpoint: string
  model?: string | null
  capabilities?: string[]
  timeout_seconds?: number
  rate_limit_per_minute?: number
  status?: TargetStatus
}

export type TargetUpdate = Partial<Omit<TargetCreate, 'project_id'>>

/**
 * Credential metadata as returned by the API.
 *
 * The plaintext credential value is intentionally absent: the backend never
 * returns it. See `docs/security-boundaries.md`.
 */
export interface Credential {
  id: UUID
  target_id: UUID
  credential_type: string
  version: number
  revoked: boolean
  created_at: string
  updated_at: string
}

export interface CredentialCreate {
  credential_type: string
  value: string
}

export interface TestSeedResult {
  created: number
  skipped: number
  invalid: number
  total: number
}

export interface SecurityTest {
  id: UUID
  project_id: UUID
  name: string
  description: string | null
  provider: string
  required_capabilities: string[]
  config: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface SecurityTestCreate {
  name: string
  description?: string | null
  provider: string
  required_capabilities?: string[]
  config?: Record<string, unknown>
}

export interface Execution {
  id: UUID
  project_id: UUID
  test_id: UUID | null
  target_id: UUID | null
  status: ExecutionStatus
  result: ExecutionResult
  started_at: string | null
  completed_at: string | null
  created_by: UUID | null
  created_at: string
  updated_at: string
}

export interface ExecutionCreate {
  test_id?: UUID | null
  target_id?: UUID | null
}

export interface Finding {
  id: UUID
  execution_id: UUID
  title: string
  description: string | null
  severity: FindingSeverity
  status: FindingStatus
  details: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface Evidence {
  id: UUID
  finding_id: UUID
  kind: string
  description: string | null
  content: Record<string, unknown>
  created_at: string
}

export interface Report {
  id: UUID
  project_id: UUID
  title: string
  format: string
  path: string
  version: number
  generated_at: string | null
  created_by: UUID | null
  created_at: string
  updated_at: string
}

export interface ReportCreate {
  title: string
  format?: string
}

export interface SeverityChange {
  title: string
  category: string
  severity_before: string
  severity_after: string
  owasp_category?: string
}

export interface ReportComparison {
  report_a_id: UUID
  report_b_id: UUID
  new_count: number
  resolved_count: number
  regressed_count: number
  improved_count: number
  unchanged_count: number
  new_findings: Array<Record<string, unknown>>
  resolved_findings: Array<Record<string, unknown>>
  regressed_findings: SeverityChange[]
  improved_findings: SeverityChange[]
  unchanged_findings: Array<Record<string, unknown>>
}

export interface Membership {
  id: UUID
  project_id: UUID
  user_id: UUID
  role: UserRole
  created_at: string
  updated_at: string
}
