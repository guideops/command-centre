const BASE = ''  // proxied to :8765 in dev; same-origin in prod

async function _fetch<T>(path: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...opts?.headers },
    ...opts,
  })
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json() as Promise<T>
}

export const api = {
  // Health
  health: () => _fetch<SystemHealth>('/api/system/health'),
  summary: () => _fetch<Summary>('/api/summary'),
  attention: () => _fetch<AttentionData>('/api/attention'),
  state: () => _fetch<Record<string, string>>('/api/system/state'),
  emergencyStop: () => _fetch<EmergencyStopResult>('/api/system/emergency-stop', { method: 'POST' }),
  emergencyResume: () => _fetch<{ resumed: boolean }>('/api/system/emergency-resume', { method: 'POST' }),

  // Sessions
  sessions: (p: { range?: string; source?: string; model?: string; page?: number; page_size?: number }) =>
    _fetch<SessionList>(`/api/sessions?${qs(p)}`),
  sessionDetails: (id: string) => _fetch<SessionDetails>(`/api/sessions/${id}/details`),
  liveSessions: () => _fetch<{ sessions: LiveSession[] }>('/api/sessions/live'),
  liveState: (sid: string) => _fetch<LiveSessionState>(`/api/sessions/live/${sid}/state`),
  sessionOutcomes: (range: string) => _fetch<{ data: OutcomeRow[] }>(`/api/sessions/outcomes?range=${range}`),
  sessionsByProject: (range: string) => _fetch<{ data: ProjectRow[] }>(`/api/sessions/by-project?range=${range}`),
  sendMessage: (sid: string, message: string) =>
    _fetch<{ queued: boolean }>(`/api/sessions/live/${sid}/message`, {
      method: 'POST',
      body: JSON.stringify({ message }),
    }),
  sync: () => _fetch<{ synced: boolean }>('/api/sync', { method: 'POST' }),

  // Usage
  usageTokens: (range: string) => _fetch<TokenUsage>(`/api/usage/tokens?range=${range}`),
  usageCache: (range: string) => _fetch<CacheStats>(`/api/usage/cache?range=${range}`),
  toolLatency: (range: string) => _fetch<{ data: ToolLatencyRow[] }>(`/api/tools/latency?range=${range}`),
  hookActivity: (range: string) => _fetch<{ data: HookRow[]; total_fires: number }>(`/api/hooks/activity?range=${range}`),
  agentFanout: (range: string) => _fetch<{ data: FanoutRow[] }>(`/api/tools/agent-fanout?range=${range}`),
  editDecisions: (range: string) => _fetch<EditDecisionData>(`/api/tools/edit-decisions?range=${range}`),
  productivity: (range: string) => _fetch<ProductivityData>(`/api/activity/productivity?range=${range}`),
  pressure: (range: string) => _fetch<PressureData>(`/api/system/pressure?range=${range}`),

  // MCP
  mcpServers: (range: string) => _fetch<{ servers: McpServer[] }>(`/api/mcp?range=${range}`),
  mcpServerTools: (server: string, range: string) =>
    _fetch<{ tools: McpTool[] }>(`/api/mcp/${encodeURIComponent(server)}/tools?range=${range}`),

  // Skills
  skills: (p?: { environment?: string; user_invocable?: boolean }) =>
    _fetch<{ skills: Skill[] }>(`/api/skills${p ? '?' + qs(p) : ''}`),
  syncSkills: () => _fetch<{ synced: number }>('/api/skills/sync', { method: 'POST' }),
  updateSkillAutonomy: (name: string, autonomy_level: string) =>
    _fetch<{ updated: boolean }>(`/api/skills/${name}/autonomy`, {
      method: 'PATCH',
      body: JSON.stringify({ autonomy_level }),
    }),

  // Context
  contextHealth: () => _fetch<ContextHealth>('/api/context/health'),

  // Decisions
  decisions: (status: string) => _fetch<{ decisions: Decision[] }>(`/api/decisions?status=${status}`),
  answerDecision: (id: number, answer: string) =>
    _fetch<{ answered: boolean }>(`/api/decisions/${id}/answer`, {
      method: 'POST',
      body: JSON.stringify({ answer }),
    }),

  // Inbox
  inbox: () => _fetch<{ messages: InboxMessage[] }>('/api/inbox?unread=1&max_age_days=30'),
  markRead: (id: number) => _fetch<{ read: boolean }>(`/api/inbox/${id}/read`, { method: 'POST' }),
  replyInbox: (id: number, body: string) =>
    _fetch<{ replied: boolean }>(`/api/inbox/${id}/reply`, {
      method: 'POST',
      body: JSON.stringify({ body }),
    }),

  // Tasks
  tasks: (p?: { status?: string; quadrant?: string }) =>
    _fetch<{ tasks: Task[] }>(`/api/tasks${p ? '?' + qs(p) : ''}`),
  createTask: (t: CreateTaskInput) =>
    _fetch<{ created: boolean }>('/api/tasks', { method: 'POST', body: JSON.stringify(t) }),
  updateTask: (id: number, data: Partial<Task>) =>
    _fetch<{ updated: boolean }>(`/api/tasks/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  deleteTask: (id: number) =>
    _fetch<{ deleted: boolean }>(`/api/tasks/${id}`, { method: 'DELETE' }),
  approveTask: (id: number) =>
    _fetch<{ approved: boolean }>(`/api/tasks/${id}/approve`, { method: 'POST' }),
  rerunTask: (id: number) =>
    _fetch<{ rerun: boolean; task_id: number }>(`/api/tasks/${id}/rerun`, { method: 'POST' }),
  triggerDispatcher: () =>
    _fetch<{ triggered: boolean }>('/api/dispatcher/trigger', { method: 'POST' }),

  // Schedules
  schedules: () => _fetch<{ schedules: Schedule[] }>('/api/schedules'),
  createSchedule: (s: CreateScheduleInput) =>
    _fetch<{ created: boolean }>('/api/schedules', { method: 'POST', body: JSON.stringify(s) }),
  updateSchedule: (id: number, data: Partial<Schedule>) =>
    _fetch<{ updated: boolean }>(`/api/schedules/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  deleteSchedule: (id: number) =>
    _fetch<{ deleted: number }>(`/api/schedules/${id}`, { method: 'DELETE' }),
  parseNlSchedule: (text: string) =>
    _fetch<{ cron: string }>('/api/schedules/parse-nl', { method: 'POST', body: JSON.stringify({ text }) }),
}

function qs(obj: Record<string, unknown>): string {
  return Object.entries(obj)
    .filter(([, v]) => v !== undefined && v !== null && v !== '')
    .map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`)
    .join('&')
}

// ─── Types ───────────────────────────────────────────────────────────────────

export interface SystemHealth {
  uptime_s: number
  memory_mb: number
  last_otel_event: string | null
  last_otel_age_s: number | null
  daemon_last_tick: string | null
  daemon_age_s: number | null
  sync_last_tick: string | null
  sync_age_s: number | null
  notifier_last_tick: string | null
  notifier_age_s: number | null
  tzname: string
}

export interface Summary {
  sessions_today: number
  tokens_today: number
  tools_today: number
  errors_today: number
}

export interface AttentionData {
  issues: AttentionIssue[]
  all_clear: boolean
}

export interface AttentionIssue {
  type: string
  count?: number
  message: string
  age_s?: number
  session_id?: string
  tool?: string
}

export interface EmergencyStopResult {
  stopped: boolean
  processes_killed: number
  interactive_spared: number
}

export interface Session {
  session_id: string
  source: string
  cwd: string | null
  git_branch: string | null
  model: string | null
  started_at: string | null
  ended_at: string | null
  input_tokens: number
  output_tokens: number
  cache_read_tokens: number
  cache_create_tokens: number
  total_tokens: number
  effective_tokens: number
  cost_usd: number
  duration_ms: number | null
  error_count: number
  rate_limit_hit: number
  stop_reason: string | null
  title: string | null
}

export interface SessionList {
  total: number
  page: number
  page_size: number
  sessions: Session[]
}

export interface SessionDetails {
  session: Session
  tools: ToolCall[]
  timeline: TimelineEntry[]
}

export interface ToolCall {
  session_id: string
  tool_use_id: string
  tool_name: string
  ts: string
  duration_ms: number | null
  error: number
}

export interface TimelineEntry {
  id: string
  name: string
  input_preview: string
  started_at: string
  ended_at: string | null
  is_error: boolean
  output_preview: string
}

export interface LiveSession {
  session_id: string
  title: string | null
  cwd: string | null
  model: string | null
  started_at: string | null
  total_tokens: number
  ended_at: string | null
  state: string | null
  current_tool: string | null
  state_updated_at: string | null
}

export interface LiveSessionState {
  session_id: string
  state: string
  current_tool: string | null
  updated_at: string
}

export interface OutcomeRow {
  date: string
  errored: number
  rate_limited: number
  truncated: number
  unfinished: number
  total: number
}

export interface ProjectRow {
  cwd: string | null
  sessions: number
  effective_tokens: number
  tool_count: number
}

export interface TokenUsage {
  data: TokenUsageRow[]
  totals: { input: number; output: number; cache_read: number; cache_create: number }
}

export interface TokenUsageRow {
  date: string
  model: string
  source: string
  input_tokens: number
  output_tokens: number
  cache_read_tokens: number
  cache_create_tokens: number
}

export interface CacheStats {
  hit_rate: number
  low_sample: boolean
  billable_tokens: number
  data: { date: string; cache_read: number; input: number; cache_create: number }[]
}

export interface ToolLatencyRow {
  tool_name: string
  calls: number
  p50: number
  p95: number
  max_ms: number
  error_rate: number
  errors: number
}

export interface HookRow {
  date: string
  fires: number
  completions: number
}

export interface FanoutRow {
  session_id: string
  title: string | null
  agent_calls: number
}

export interface EditDecisionData {
  data: { decision: string; count: number }[]
  total: number
  low_sample: boolean
}

export interface ProductivityData {
  totals: Record<string, number>
  daily: { date: string; metric_name: string; total: number }[]
}

export interface PressureData {
  retry_exhaustion_count: number
  compaction_count: number
  retry_threshold: number
  recent_errors: { timestamp: string; error_message: string; status_code: number; attempt_count: number }[]
}

export interface McpServer {
  server: string
  total_calls: number
  avg_latency: number
  p95: number
  errors: number
}

export interface McpTool {
  tool: string
  calls: number
  p50: number
  p95: number
  max_ms: number
  error_rate: number
  errors: number
}

export interface Skill {
  name: string
  environment: string
  description: string | null
  path: string | null
  autonomy_level: string
  user_invocable: number
  script_count: number
  last_modified: string | null
}

export interface ContextHealth {
  settings_exists: boolean
  claude_md_exists: boolean
  mcp_server_count?: number
  hook_count?: number
  settings_size_bytes?: number
  claude_md_lines?: number
  claude_md_size_bytes?: number
}

export interface Decision {
  id: number
  task_id: number | null
  session_id: string | null
  prompt: string
  answer: string | null
  status: string
  created_at: string
  answered_at: string | null
}

export interface InboxMessage {
  id: number
  task_id: number | null
  session_id: string | null
  direction: string
  body: string
  read: number
  created_at: string
}

export interface Task {
  id: number
  title: string
  description: string | null
  status: string
  priority: number
  assigned_skill: string | null
  model: string | null
  execution_mode: string
  scheduled_for: string | null
  requires_approval: number
  risk_level: string
  dry_run: number
  quadrant: string
  approved_at: string | null
  session_id: string | null
  started_at: string | null
  completed_at: string | null
  duration_ms: number | null
  cost_usd: number | null
  output_summary: string | null
  error_message: string | null
  consecutive_failures: number
  created_at: string
}

export interface CreateTaskInput {
  title: string
  description?: string
  priority?: number
  quadrant?: string
  requires_approval?: boolean
  risk_level?: string
  dry_run?: boolean
  model?: string
  execution_mode?: string
  assigned_skill?: string
  scheduled_for?: string
}

export interface Schedule {
  id: number
  name: string
  cron_expression: string | null
  task_title: string | null
  task_description: string | null
  assigned_skill: string | null
  enabled: number
  next_run_at: string | null
  last_run_at: string | null
  created_at: string
}

export interface CreateScheduleInput {
  name: string
  cron_expression?: string
  task_title?: string
  task_description?: string
  assigned_skill?: string
  enabled?: boolean
}
