import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../lib/api'

// ─── System ──────────────────────────────────────────────────────────────────
export const useHealth = () => useQuery({ queryKey: ['health'], queryFn: api.health, refetchInterval: 15_000 })
export const useSummary = () => useQuery({ queryKey: ['summary'], queryFn: api.summary })
export const useAttention = () => useQuery({ queryKey: ['attention'], queryFn: api.attention, refetchInterval: 15_000 })
export const useSystemState = () => useQuery({ queryKey: ['state'], queryFn: api.state })

// ─── Sessions ────────────────────────────────────────────────────────────────
export const useSessions = (params: Parameters<typeof api.sessions>[0] & { page_size?: number }) =>
  useQuery({ queryKey: ['sessions', params], queryFn: () => api.sessions(params) })

export const useSessionDetails = (id: string) =>
  useQuery({ queryKey: ['session', id], queryFn: () => api.sessionDetails(id), enabled: !!id })

export const useLiveSessions = () =>
  useQuery({ queryKey: ['live-sessions'], queryFn: api.liveSessions, refetchInterval: 5_000 })

export const useLiveState = (sid: string) =>
  useQuery({ queryKey: ['live-state', sid], queryFn: () => api.liveState(sid), refetchInterval: 3_000, enabled: !!sid })

export const useSessionOutcomes = (range: string) =>
  useQuery({ queryKey: ['outcomes', range], queryFn: () => api.sessionOutcomes(range) })

export const useSessionsByProject = (range: string) =>
  useQuery({ queryKey: ['by-project', range], queryFn: () => api.sessionsByProject(range) })

// ─── Usage ───────────────────────────────────────────────────────────────────
export const useTokenUsage = (range: string) =>
  useQuery({ queryKey: ['tokens', range], queryFn: () => api.usageTokens(range) })

export const useCacheStats = (range: string) =>
  useQuery({ queryKey: ['cache', range], queryFn: () => api.usageCache(range) })

export const useToolLatency = (range: string) =>
  useQuery({ queryKey: ['latency', range], queryFn: () => api.toolLatency(range) })

export const useHookActivity = (range: string) =>
  useQuery({ queryKey: ['hooks', range], queryFn: () => api.hookActivity(range) })

export const useAgentFanout = (range: string) =>
  useQuery({ queryKey: ['fanout', range], queryFn: () => api.agentFanout(range) })

export const useEditDecisions = (range: string) =>
  useQuery({ queryKey: ['edit-decisions', range], queryFn: () => api.editDecisions(range) })

export const useProductivity = (range: string) =>
  useQuery({ queryKey: ['productivity', range], queryFn: () => api.productivity(range) })

export const usePressure = (range: string) =>
  useQuery({ queryKey: ['pressure', range], queryFn: () => api.pressure(range) })

// ─── MCP ─────────────────────────────────────────────────────────────────────
export const useMcpServers = (range: string) =>
  useQuery({ queryKey: ['mcp', range], queryFn: () => api.mcpServers(range) })

export const useMcpServerTools = (server: string, range: string) =>
  useQuery({
    queryKey: ['mcp-tools', server, range],
    queryFn: () => api.mcpServerTools(server, range),
    enabled: !!server,
  })

// ─── Skills ──────────────────────────────────────────────────────────────────
export const useSkills = (params?: Parameters<typeof api.skills>[0]) =>
  useQuery({ queryKey: ['skills', params], queryFn: () => api.skills(params) })

export const useContextHealth = () =>
  useQuery({ queryKey: ['context-health'], queryFn: api.contextHealth })

// ─── Decisions ───────────────────────────────────────────────────────────────
export const useDecisions = (status = 'pending') =>
  useQuery({ queryKey: ['decisions', status], queryFn: () => api.decisions(status), refetchInterval: 5_000 })

export const useAnswerDecision = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, answer }: { id: number; answer: string }) => api.answerDecision(id, answer),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['decisions'] }) },
  })
}

// ─── Inbox ───────────────────────────────────────────────────────────────────
export const useInbox = () =>
  useQuery({ queryKey: ['inbox'], queryFn: api.inbox, refetchInterval: 10_000 })

export const useMarkRead = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => api.markRead(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['inbox'] }) },
  })
}

export const useReplyInbox = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, body }: { id: number; body: string }) => api.replyInbox(id, body),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['inbox'] }) },
  })
}

// ─── Tasks ───────────────────────────────────────────────────────────────────
export const useTasks = (params?: Parameters<typeof api.tasks>[0]) =>
  useQuery({ queryKey: ['tasks', params], queryFn: () => api.tasks(params), refetchInterval: 10_000 })

export const useCreateTask = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: api.createTask,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['tasks'] }) },
  })
}

export const useApproveTask = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => api.approveTask(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['tasks'] }) },
  })
}

export const useRerunTask = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => api.rerunTask(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['tasks'] }) },
  })
}

export const useDeleteTask = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => api.deleteTask(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['tasks'] }) },
  })
}

// ─── Schedules ───────────────────────────────────────────────────────────────
export const useSchedules = () =>
  useQuery({ queryKey: ['schedules'], queryFn: api.schedules })

export const useCreateSchedule = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: api.createSchedule,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['schedules'] }) },
  })
}

export const useUpdateSchedule = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: Parameters<typeof api.updateSchedule>[1] }) =>
      api.updateSchedule(id, data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['schedules'] }) },
  })
}

export const useDeleteSchedule = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => api.deleteSchedule(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['schedules'] }) },
  })
}
