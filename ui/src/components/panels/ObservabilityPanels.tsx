import { useState } from 'react'
import {
  useCacheStats, useSessionOutcomes, useToolLatency, useHookActivity,
  useSessionsByProject, useAgentFanout, useEditDecisions, useProductivity, usePressure,
} from '@/hooks/useQueries'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { fmtTokens, fmtMs, projectName } from '@/lib/utils'
import { cn } from '@/lib/utils'

type Range = 'today' | '7d' | '30d'

function RangeToggle({ value, onChange }: { value: Range; onChange: (r: Range) => void }) {
  return (
    <div className="flex gap-1">
      {(['today', '7d', '30d'] as Range[]).map(r => (
        <button
          key={r}
          onClick={() => onChange(r)}
          className={`px-2 py-0.5 text-xs rounded font-mono ${value === r ? 'bg-surface-2 text-text border border-border' : 'text-text-dim hover:text-text'}`}
        >
          {r}
        </button>
      ))}
    </div>
  )
}

// ─── Cache Efficiency ────────────────────────────────────────────────────────

export function CacheEfficiencyCard() {
  const [range, setRange] = useState<Range>('7d')
  const { data, isLoading } = useCacheStats(range)

  const hitRate = data ? Math.round(data.hit_rate * 100) : null
  const target = 70

  return (
    <Card className="h-full">
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>Cache Efficiency</CardTitle>
          <RangeToggle value={range} onChange={setRange} />
        </div>
      </CardHeader>
      <CardContent>
        {isLoading ? <div className="skeleton h-28 rounded-lg" /> : (
          <>
            <div className="flex items-end gap-2 mb-4">
              <span className={cn('text-4xl font-bold font-mono', hitRate != null && hitRate >= target ? 'text-green' : 'text-amber')}>
                {hitRate != null ? `${hitRate}%` : '—'}
              </span>
              <span className="text-xs text-text-dim mb-1.5">hit rate (target {target}%)</span>
              {data?.low_sample && <Badge variant="amber">low sample</Badge>}
            </div>
            <div className="flex items-end gap-0.5 h-16">
              {data?.data.map((d, i) => {
                const total = (d.cache_read || 0) + (d.input || 0) + (d.cache_create || 0)
                const rate = total > 0 ? d.cache_read / total : 0
                return (
                  <div key={i} className="flex-1 flex flex-col justify-end" title={`${d.date}: ${Math.round(rate * 100)}%`}>
                    <div
                      className={cn('w-full rounded-t-sm transition-all', rate >= 0.7 ? 'bg-green/60' : 'bg-amber/60')}
                      style={{ height: `${Math.max(rate * 64, 2)}px` }}
                    />
                  </div>
                )
              })}
            </div>
            <div className="mt-2 border-t border-dashed border-border relative" style={{ marginTop: '4px' }}>
              <span className="absolute -top-2 right-0 text-[10px] text-text-subtle font-mono">70% target</span>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  )
}

// ─── Session Outcomes ────────────────────────────────────────────────────────

const OUTCOME_COLORS: Record<string, string> = {
  errored: '#ef4444',
  rate_limited: '#f59e0b',
  truncated: '#f97316',
  unfinished: '#6b7280',
  ok: '#10b981',
}

export function SessionOutcomesCard() {
  const [range, setRange] = useState<Range>('7d')
  const { data, isLoading } = useSessionOutcomes(range)

  const days = data?.data || []
  const maxTotal = Math.max(...days.map(d => d.total), 1)

  return (
    <Card className="h-full">
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>Session Outcomes</CardTitle>
          <RangeToggle value={range} onChange={setRange} />
        </div>
        <div className="flex gap-3 flex-wrap">
          {Object.entries(OUTCOME_COLORS).map(([k, c]) => (
            <div key={k} className="flex items-center gap-1 text-xs text-text-dim">
              <span className="w-2 h-2 rounded-sm" style={{ background: c }} />
              {k}
            </div>
          ))}
        </div>
      </CardHeader>
      <CardContent>
        {isLoading ? <div className="skeleton h-32 rounded-lg" /> : days.length === 0 ? (
          <div className="text-center text-text-subtle text-sm py-8">No session data</div>
        ) : (
          <div className="flex items-end gap-1 h-32">
            {days.map((d) => {
              const ok = Math.max(d.total - d.errored - d.rate_limited - d.truncated - d.unfinished, 0)
              const segs = [
                { key: 'errored', val: d.errored },
                { key: 'rate_limited', val: d.rate_limited },
                { key: 'truncated', val: d.truncated },
                { key: 'unfinished', val: d.unfinished },
                { key: 'ok', val: ok },
              ]
              return (
                <div key={d.date} className="flex-1 flex flex-col justify-end" title={d.date}>
                  {segs.map(s => s.val > 0 && (
                    <div
                      key={s.key}
                      style={{
                        height: `${(s.val / maxTotal) * 128}px`,
                        background: OUTCOME_COLORS[s.key],
                      }}
                      className="w-full first:rounded-t-sm"
                    />
                  ))}
                </div>
              )
            })}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

// ─── Tool Latency ────────────────────────────────────────────────────────────

export function ToolLatencyCard() {
  const [range, setRange] = useState<Range>('7d')
  const { data, isLoading } = useToolLatency(range)

  return (
    <Card className="h-full">
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>Tool Latency</CardTitle>
          <RangeToggle value={range} onChange={setRange} />
        </div>
      </CardHeader>
      <CardContent>
        {isLoading ? <div className="skeleton h-40 rounded-lg" /> : (
          <div className="overflow-auto max-h-64">
            {(data?.data || []).length === 0 ? (
              <div className="text-center text-text-subtle text-sm py-8">No tool data</div>
            ) : (
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-text-subtle">
                    <th className="text-left pb-2">Tool</th>
                    <th className="text-right pb-2">p50</th>
                    <th className="text-right pb-2">p95</th>
                    <th className="text-right pb-2">err%</th>
                    <th className="text-right pb-2">N</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {(data?.data || []).map(r => (
                    <tr key={r.tool_name} className="hover:bg-surface-2/50">
                      <td className="py-1.5 font-mono text-text">
                        {r.p95 >= 10000 ? '🔴' : r.p95 < 500 ? '🟢' : ''}
                        {' '}{r.tool_name}
                      </td>
                      <td className="py-1.5 text-right font-mono text-text-dim">{fmtMs(r.p50)}</td>
                      <td className={cn('py-1.5 text-right font-mono', r.p95 >= 10000 ? 'text-red' : r.p95 < 500 ? 'text-green' : 'text-text')}>{fmtMs(r.p95)}</td>
                      <td className={cn('py-1.5 text-right font-mono', r.error_rate > 0.1 ? 'text-red' : 'text-text-dim')}>{Math.round(r.error_rate * 100)}%</td>
                      <td className="py-1.5 text-right text-text-subtle">{r.calls}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

// ─── Hook Activity ───────────────────────────────────────────────────────────

export function HookActivityCard() {
  const [range, setRange] = useState<Range>('7d')
  const { data, isLoading } = useHookActivity(range)

  return (
    <Card className="h-full">
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>Hook Activity</CardTitle>
          <RangeToggle value={range} onChange={setRange} />
        </div>
      </CardHeader>
      <CardContent>
        {isLoading ? <div className="skeleton h-28 rounded-lg" /> : (
          data?.total_fires === 0 ? (
            <div className="text-center py-8 text-text-subtle text-sm">
              <p>No hook events yet</p>
              <p className="text-xs mt-1">Enable OTEL and add hooks to see activity</p>
            </div>
          ) : (
            <div className="space-y-2">
              <div className="text-2xl font-bold font-mono">{data?.total_fires || 0} <span className="text-sm font-normal text-text-dim">fires</span></div>
              <div className="flex items-end gap-0.5 h-16">
                {(data?.data || []).map((d, i) => (
                  <div key={i} className="flex-1 flex flex-col justify-end gap-0.5" title={d.date}>
                    <div className="w-full rounded-t-sm bg-cyan/50" style={{ height: `${Math.max((d.fires / (data?.total_fires || 1)) * 64 * (data?.data.length || 1), 2)}px` }} />
                  </div>
                ))}
              </div>
            </div>
          )
        )}
      </CardContent>
    </Card>
  )
}

// ─── Project Breakdown ───────────────────────────────────────────────────────

export function ProjectBreakdownCard() {
  const [range, setRange] = useState<Range>('7d')
  const { data, isLoading } = useSessionsByProject(range)
  const rows = data?.data || []
  const totalTokens = rows.reduce((s, r) => s + (r.effective_tokens || 0), 0)

  return (
    <Card className="h-full">
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>Projects</CardTitle>
          <RangeToggle value={range} onChange={setRange} />
        </div>
      </CardHeader>
      <CardContent>
        {isLoading ? <div className="skeleton h-40 rounded-lg" /> : rows.length === 0 ? (
          <div className="text-center py-8 text-text-subtle text-sm">No project data</div>
        ) : (
          <div className="space-y-2 max-h-56 overflow-y-auto">
            {rows.map((r, i) => {
              const pct = totalTokens > 0 ? (r.effective_tokens / totalTokens) * 100 : 0
              return (
                <div key={i} className="space-y-1">
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-mono text-text truncate max-w-[160px]">{projectName(r.cwd)}</span>
                    <div className="flex gap-3 text-text-dim">
                      <span>{r.sessions} sess</span>
                      <span>{fmtTokens(r.effective_tokens)}</span>
                      <span className="text-text-subtle">{pct.toFixed(0)}%</span>
                    </div>
                  </div>
                  <div className="h-1 bg-surface-2 rounded-full overflow-hidden">
                    <div className="h-full bg-accent/60 rounded-full" style={{ width: `${pct}%` }} />
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

// ─── Agent Fanout ────────────────────────────────────────────────────────────

export function AgentFanoutCard() {
  const [range, setRange] = useState<Range>('7d')
  const { data, isLoading } = useAgentFanout(range)

  return (
    <Card className="h-full">
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>Agent Fanout</CardTitle>
          <RangeToggle value={range} onChange={setRange} />
        </div>
      </CardHeader>
      <CardContent>
        {isLoading ? <div className="skeleton h-32 rounded-lg" /> : (data?.data || []).length === 0 ? (
          <div className="text-center py-8 text-text-subtle text-sm">No Agent calls yet</div>
        ) : (
          <div className="space-y-1.5 max-h-48 overflow-y-auto">
            {(data?.data || []).map((r, i) => (
              <div key={i} className="flex items-center gap-3 text-xs">
                <span className="flex-1 font-mono text-text truncate">
                  {r.title || <span className="text-text-subtle">session:{r.session_id.slice(0, 8)}</span>}
                </span>
                <Badge variant="purple">{r.agent_calls} subagents</Badge>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

// ─── Edit Acceptance ─────────────────────────────────────────────────────────

export function EditAcceptanceCard() {
  const [range, setRange] = useState<Range>('7d')
  const { data, isLoading } = useEditDecisions(range)

  const accept = data?.data.find(d => d.decision === 'accept')?.count || 0
  const reject = data?.data.find(d => d.decision === 'reject')?.count || 0
  const total = accept + reject
  const rate = total > 0 ? Math.round((accept / total) * 100) : null

  return (
    <Card className="h-full">
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>Edit Acceptance</CardTitle>
          <RangeToggle value={range} onChange={setRange} />
        </div>
      </CardHeader>
      <CardContent>
        {isLoading ? <div className="skeleton h-20 rounded-lg" /> : (
          <div className="space-y-3">
            {data?.low_sample && <Badge variant="amber">low sample (N&lt;10)</Badge>}
            {rate == null ? (
              <div className="text-center py-6 text-text-subtle text-sm">No edit decisions yet</div>
            ) : (
              <>
                <div className="flex items-end gap-2">
                  <span className={cn('text-3xl font-bold font-mono', rate >= 80 ? 'text-green' : rate >= 60 ? 'text-amber' : 'text-red')}>
                    {rate}%
                  </span>
                  <span className="text-xs text-text-dim mb-1">acceptance rate</span>
                </div>
                <div className="flex gap-2 text-xs">
                  <div className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-sm bg-green" /><span className="text-text-dim">{accept} accepted</span></div>
                  <div className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-sm bg-red" /><span className="text-text-dim">{reject} rejected</span></div>
                </div>
                <div className="h-1.5 bg-surface-2 rounded-full overflow-hidden">
                  <div className="h-full bg-green rounded-full" style={{ width: `${rate}%` }} />
                </div>
              </>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

// ─── Productivity ────────────────────────────────────────────────────────────

export function ProductivityCard() {
  const [range, setRange] = useState<Range>('7d')
  const { data, isLoading } = useProductivity(range)

  const t = data?.totals || {}
  const commits = t['claude_code.commit.count'] || 0
  const prs = t['claude_code.pull_request.count'] || 0
  const lines = t['claude_code.lines_of_code.count'] || 0
  const allZero = commits === 0 && prs === 0 && lines === 0

  return (
    <Card className="h-full">
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>Productivity</CardTitle>
          <RangeToggle value={range} onChange={setRange} />
        </div>
      </CardHeader>
      <CardContent>
        {isLoading ? <div className="skeleton h-20 rounded-lg" /> : allZero ? (
          <div className="text-center py-6 text-text-subtle text-sm">
            <p>No OTEL productivity data</p>
            <p className="text-xs mt-1">Enable telemetry to track commits & PRs</p>
          </div>
        ) : (
          <div className="flex gap-4">
            <div className="text-center">
              <div className="text-2xl font-bold font-mono text-text">{commits}</div>
              <div className="text-xs text-text-dim">commits</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold font-mono text-text">{prs}</div>
              <div className="text-xs text-text-dim">PRs</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold font-mono text-text">{fmtTokens(lines)}</div>
              <div className="text-xs text-text-dim">lines</div>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

// ─── Pressure Panel ──────────────────────────────────────────────────────────

export function PressurePanel() {
  const [range, setRange] = useState<Range>('7d')
  const { data, isLoading } = usePressure(range)

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>System Pressure</CardTitle>
          <RangeToggle value={range} onChange={setRange} />
        </div>
      </CardHeader>
      <CardContent>
        {isLoading ? <div className="skeleton h-24 rounded-lg" /> : (
          <div className="space-y-4">
            <div className="flex gap-6">
              <div>
                <div className={cn('text-2xl font-bold font-mono', (data?.retry_exhaustion_count || 0) > 0 ? 'text-red' : 'text-text')}>
                  {data?.retry_exhaustion_count || 0}
                </div>
                <div className="text-xs text-text-dim">retry exhaustions <span className="text-text-subtle">(≥{data?.retry_threshold} retries)</span></div>
              </div>
              <div>
                <div className={cn('text-2xl font-bold font-mono', (data?.compaction_count || 0) > 5 ? 'text-amber' : 'text-text')}>
                  {data?.compaction_count || 0}
                </div>
                <div className="text-xs text-text-dim">compactions</div>
              </div>
            </div>
            {(data?.recent_errors || []).length > 0 && (
              <div>
                <div className="kicker mb-2">Recent API Errors</div>
                <div className="space-y-1.5 max-h-40 overflow-y-auto">
                  {data!.recent_errors.map((e, i) => (
                    <div key={i} className="flex items-center gap-2 text-xs">
                      <Badge variant="red">{e.status_code || '?'}</Badge>
                      <span className="text-text-dim truncate flex-1">{e.error_message}</span>
                      <span className="text-text-subtle flex-shrink-0">{e.attempt_count}× retries</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
