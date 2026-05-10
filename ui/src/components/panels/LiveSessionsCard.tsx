import { useState } from 'react'
import { useLiveSessions, useLiveState, useSessionDetails } from '@/hooks/useQueries'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card'
import { Sheet } from '@/components/ui/Sheet'
import { Badge, StatePill } from '@/components/ui/Badge'
import { Tooltip } from '@/components/ui/Tooltip'
import { Button } from '@/components/ui/Button'
import { fmtTokens, relativeTime, absoluteTime, projectName } from '@/lib/utils'
import { api } from '@/lib/api'
import type { LiveSession } from '@/lib/api'
import { Terminal, Send } from 'lucide-react'

function SessionDrawer({ session, onClose }: { session: LiveSession; onClose: () => void }) {
  const { data: details } = useSessionDetails(session.session_id)
  const { data: state } = useLiveState(session.session_id)
  const [msg, setMsg] = useState('')
  const [sending, setSending] = useState(false)
  const isStream = true // TODO: check execution_mode from task

  const send = async () => {
    if (!msg.trim()) return
    setSending(true)
    try {
      await api.sendMessage(session.session_id, msg)
      setMsg('')
    } finally {
      setSending(false)
    }
  }

  return (
    <Sheet open title={session.title || `Session ${session.session_id.slice(0, 8)}`} onClose={onClose} width="w-[520px]">
      <div className="space-y-4">
        <div className="flex flex-wrap gap-2">
          <Badge variant="default">{session.model || 'unknown'}</Badge>
          {state?.state && <StatePill state={state.state} />}
          {state?.current_tool && <Badge variant="cyan">{state.current_tool}</Badge>}
        </div>

        <div className="text-xs text-text-dim space-y-1">
          <div className="font-mono">{projectName(session.cwd)}</div>
          <div>Started {relativeTime(session.started_at)}</div>
          <div>{fmtTokens(session.total_tokens)} tokens</div>
        </div>

        <div>
          <div className="kicker mb-2">Tool Timeline</div>
          <div className="space-y-1.5 max-h-72 overflow-y-auto pr-1">
            {details?.timeline.length === 0 && (
              <p className="text-xs text-text-subtle py-4 text-center">No tool calls yet</p>
            )}
            {details?.timeline.map((entry, i) => (
              <div key={i} className="rounded-lg border border-border bg-surface p-3 text-xs">
                <div className="flex items-center justify-between mb-1">
                  <span className="font-mono font-medium text-text">{entry.name}</span>
                  <div className="flex items-center gap-2">
                    {entry.is_error && <Badge variant="red">error</Badge>}
                    <span className="text-text-subtle">{relativeTime(entry.started_at)}</span>
                  </div>
                </div>
                {entry.input_preview && (
                  <div className="text-text-subtle truncate mt-1">{entry.input_preview}</div>
                )}
                {entry.output_preview && (
                  <div className="text-text-dim truncate mt-0.5">{entry.output_preview}</div>
                )}
              </div>
            ))}
          </div>
        </div>

        {isStream ? (
          <div className="border-t border-border pt-4">
            <div className="kicker mb-2">Send a follow-up</div>
            <div className="flex gap-2">
              <input
                value={msg}
                onChange={e => setMsg(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() } }}
                placeholder="Type a message…"
                className="flex-1 bg-surface-2 border border-border rounded-lg px-3 py-2 text-xs text-text placeholder:text-text-subtle outline-none focus:border-border-glow"
              />
              <Button size="sm" variant="primary" onClick={send} disabled={sending || !msg.trim()}>
                <Send size={12} />
              </Button>
            </div>
          </div>
        ) : (
          <p className="text-xs text-text-subtle border-t border-border pt-4">
            Read-only — this task was queued as One-shot. Re-queue as Interactive to reply from the dashboard.
          </p>
        )}
      </div>
    </Sheet>
  )
}

export function LiveSessionsCard() {
  const { data, isLoading } = useLiveSessions()
  const [selected, setSelected] = useState<LiveSession | null>(null)

  const sessions = data?.sessions || []

  return (
    <>
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-green animate-pulse" />
            <CardTitle>Live Sessions</CardTitle>
            <Badge variant="default">{sessions.length}</Badge>
          </div>
        </CardHeader>
        <CardContent>
          {isLoading && <div className="skeleton h-20 rounded-lg" />}
          {!isLoading && sessions.length === 0 && (
            <div className="flex flex-col items-center gap-2 py-8 text-text-subtle">
              <Terminal size={24} className="opacity-30" />
              <p className="text-sm">No active sessions</p>
            </div>
          )}
          <div className="space-y-2">
            {sessions.map(s => (
              <button
                key={s.session_id}
                onClick={() => setSelected(s)}
                className="w-full text-left rounded-lg border border-border bg-surface hover:border-border-glow hover:bg-surface-2/50 p-3 transition-all duration-150"
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm text-text truncate max-w-[250px]">
                    {s.title || <span className="text-text-subtle font-mono">{s.session_id.slice(0, 12)}</span>}
                  </span>
                  <div className="flex items-center gap-2">
                    {s.state && <StatePill state={s.state} />}
                    <Tooltip content={absoluteTime(s.started_at)}>
                      <span className="text-xs text-text-subtle">{relativeTime(s.started_at)}</span>
                    </Tooltip>
                  </div>
                </div>
                <div className="flex items-center gap-3 mt-1">
                  <span className="text-xs text-text-dim font-mono">{projectName(s.cwd)}</span>
                  <Badge variant="muted">{s.model?.split('-').slice(-2).join('-') || '?'}</Badge>
                  <span className="text-xs text-text-subtle ml-auto">{fmtTokens(s.total_tokens)} tok</span>
                </div>
              </button>
            ))}
          </div>
        </CardContent>
      </Card>
      {selected && <SessionDrawer session={selected} onClose={() => setSelected(null)} />}
    </>
  )
}
