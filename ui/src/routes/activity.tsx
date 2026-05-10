import { useState, useEffect, useRef } from 'react'
import { motion } from 'framer-motion'
import { useSessions, useSessionOutcomes, useTokenUsage } from '@/hooks/useQueries'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card'
import { CollapsibleSection } from '@/components/ui/CollapsibleSection'
import { Badge } from '@/components/ui/Badge'
import { relativeTime, absoluteTime, fmtTokens, projectName } from '@/lib/utils'
import { cn } from '@/lib/utils'
import { Radio } from 'lucide-react'

const fadeUp = { initial: { opacity: 0, y: 6 }, animate: { opacity: 1, y: 0 }, transition: { duration: 0.3 } }

// ─── Heatmap ─────────────────────────────────────────────────────────────────

function HeatmapGrid() {
  const { data } = useSessionOutcomes('30d')

  const days = data?.data || []
  const maxTotal = Math.max(...days.map(d => d.total), 1)

  return (
    <Card>
      <CardHeader><CardTitle>30-Day Activity</CardTitle></CardHeader>
      <CardContent>
        <div className="flex flex-wrap gap-1">
          {days.map(d => {
            const intensity = d.total / maxTotal
            return (
              <div
                key={d.date}
                title={`${d.date}: ${d.total} sessions`}
                className="w-4 h-4 rounded-sm"
                style={{
                  background: intensity === 0
                    ? 'var(--surface-2)'
                    : `rgba(77, 124, 255, ${0.15 + intensity * 0.85})`
                }}
              />
            )
          })}
        </div>
      </CardContent>
    </Card>
  )
}

// ─── OTEL Firehose ────────────────────────────────────────────────────────────

interface OtelEvent {
  id: number
  event_name: string
  session_id: string | null
  timestamp: string | null
  tool_name: string | null
  received_at: string
}

function OtelPanel() {
  const [events, setEvents] = useState<OtelEvent[]>([])
  const [filter, setFilter] = useState('')
  const listRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const es = new EventSource('/api/firehose')
    es.onmessage = e => {
      try {
        const data = JSON.parse(e.data) as OtelEvent
        setEvents(prev => [data, ...prev].slice(0, 200))
      } catch {}
    }
    return () => es.close()
  }, [])

  const filtered = filter
    ? events.filter(e => e.event_name?.includes(filter) || e.tool_name?.includes(filter))
    : events

  const colorFor = (name: string) => {
    if (name.includes('error')) return 'text-red'
    if (name.includes('tool')) return 'text-cyan'
    if (name.includes('api')) return 'text-accent'
    if (name.includes('hook')) return 'text-green'
    return 'text-text-dim'
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Radio size={14} className="text-green animate-pulse" />
            <CardTitle>OTEL Firehose</CardTitle>
            <Badge variant="default">{events.length}</Badge>
          </div>
          <input
            value={filter}
            onChange={e => setFilter(e.target.value)}
            placeholder="Filter events…"
            className="px-2 py-1 text-xs bg-surface-2 border border-border rounded-md text-text outline-none focus:border-border-glow w-36"
          />
        </div>
      </CardHeader>
      <CardContent>
        <div ref={listRef} className="space-y-0.5 max-h-72 overflow-y-auto font-mono text-xs">
          {filtered.length === 0 && (
            <div className="text-center py-8 text-text-subtle">
              {events.length === 0 ? 'Waiting for OTEL events…' : 'No matching events'}
            </div>
          )}
          {filtered.slice(0, 100).map(e => (
            <div key={e.id} className="flex items-center gap-2 py-0.5 hover:bg-surface-2/50 rounded px-1">
              <span className="text-text-subtle flex-shrink-0 w-20 truncate">{e.received_at?.slice(11, 19)}</span>
              <span className={cn('flex-shrink-0 w-36 truncate', colorFor(e.event_name))}>{e.event_name}</span>
              {e.tool_name && <span className="text-text-dim truncate">{e.tool_name}</span>}
              {e.session_id && <span className="text-text-subtle ml-auto flex-shrink-0">{e.session_id.slice(0, 8)}</span>}
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}

// ─── Sessions Table ───────────────────────────────────────────────────────────

function SessionsTable() {
  const [search, setSearch] = useState('')
  const [range, setRange] = useState('7d')
  const [page, setPage] = useState(1)

  const { data, isLoading } = useSessions({ range, page, page_size: 30 })
  const sessions = (data?.sessions || []).filter(s =>
    !search || s.title?.toLowerCase().includes(search.toLowerCase()) ||
    s.session_id.includes(search) || s.cwd?.includes(search)
  )

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between gap-3">
          <CardTitle>All Sessions</CardTitle>
          <div className="flex items-center gap-2">
            <input
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Search…"
              className="px-2 py-1 text-xs bg-surface-2 border border-border rounded-md text-text outline-none focus:border-border-glow w-40"
            />
            {(['7d', '30d', 'today'] as const).map(r => (
              <button
                key={r}
                onClick={() => { setRange(r); setPage(1) }}
                className={`px-2 py-1 text-xs rounded font-mono ${range === r ? 'bg-surface-2 text-text border border-border' : 'text-text-dim hover:text-text'}`}
              >
                {r}
              </button>
            ))}
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {isLoading ? <div className="skeleton h-40 rounded-lg" /> : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-text-subtle border-b border-border">
                    <th className="text-left pb-2 font-normal">Session</th>
                    <th className="text-left pb-2 font-normal">Project</th>
                    <th className="text-left pb-2 font-normal">Model</th>
                    <th className="text-right pb-2 font-normal">Tokens</th>
                    <th className="text-right pb-2 font-normal">Cost</th>
                    <th className="text-right pb-2 font-normal">Started</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/50">
                  {sessions.map(s => (
                    <tr key={s.session_id} className="hover:bg-surface-2/30">
                      <td className="py-2 max-w-[200px]">
                        <span className="truncate block text-text">{s.title || <span className="text-text-subtle font-mono">{s.session_id.slice(0, 12)}</span>}</span>
                      </td>
                      <td className="py-2 font-mono text-text-dim">{projectName(s.cwd)}</td>
                      <td className="py-2 text-text-subtle">{s.model?.split('-').slice(-2).join('-')}</td>
                      <td className="py-2 text-right font-mono text-text-dim">{fmtTokens(s.total_tokens)}</td>
                      <td className="py-2 text-right font-mono text-text-subtle">{s.cost_usd > 0 ? `$${s.cost_usd.toFixed(3)}` : '—'}</td>
                      <td className="py-2 text-right text-text-subtle" title={absoluteTime(s.started_at)}>{relativeTime(s.started_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {(data?.total || 0) > 30 && (
              <div className="flex items-center justify-between mt-4 text-xs text-text-dim">
                <span>{data?.total} total</span>
                <div className="flex gap-1">
                  <button disabled={page <= 1} onClick={() => setPage(p => p - 1)} className="px-2 py-1 border border-border rounded hover:bg-surface-2 disabled:opacity-40">Prev</button>
                  <span className="px-2 py-1">Page {page}</span>
                  <button disabled={page * 30 >= (data?.total || 0)} onClick={() => setPage(p => p + 1)} className="px-2 py-1 border border-border rounded hover:bg-surface-2 disabled:opacity-40">Next</button>
                </div>
              </div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  )
}

export function ActivityPage() {
  return (
    <motion.div {...fadeUp} className="space-y-4">
      <CollapsibleSection id="patterns" title="Patterns" defaultOpen>
        <HeatmapGrid />
      </CollapsibleSection>

      <CollapsibleSection id="firehose" title="Telemetry Firehose" defaultOpen>
        <OtelPanel />
      </CollapsibleSection>

      <CollapsibleSection id="all-sessions" title="All Sessions" defaultOpen>
        <SessionsTable />
      </CollapsibleSection>
    </motion.div>
  )
}
