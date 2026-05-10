import { useState } from 'react'
import { useDecisions, useAnswerDecision, useInbox, useMarkRead, useReplyInbox } from '@/hooks/useQueries'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { relativeTime } from '@/lib/utils'
import { MessageSquare, Inbox, Send } from 'lucide-react'

// ─── Decisions ───────────────────────────────────────────────────────────────

function DecisionModal({
  prompt,
  onSubmit,
  onClose,
}: { prompt: string; onSubmit: (answer: string) => void; onClose: () => void }) {
  const [answer, setAnswer] = useState('')
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm" onClick={onClose}>
      <div
        className="bg-surface border border-border rounded-xl p-6 w-full max-w-md shadow-2xl"
        onClick={e => e.stopPropagation()}
      >
        <h3 className="text-sm font-semibold mb-3">Answer Decision</h3>
        <p className="text-xs text-text-dim mb-4 bg-surface-2 rounded-lg p-3 border border-border">{prompt}</p>
        <input
          autoFocus
          value={answer}
          onChange={e => setAnswer(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') { onSubmit(answer); onClose() } if (e.key === 'Escape') onClose() }}
          placeholder="Your answer…"
          className="w-full bg-surface-2 border border-border rounded-lg px-3 py-2 text-sm text-text placeholder:text-text-subtle outline-none focus:border-border-glow mb-4"
        />
        <div className="flex gap-2 justify-end">
          <Button variant="ghost" size="sm" onClick={onClose}>Cancel</Button>
          <Button variant="primary" size="sm" onClick={() => { onSubmit(answer); onClose() }} disabled={!answer.trim()}>
            Submit
          </Button>
        </div>
      </div>
    </div>
  )
}

export function DecisionsCard() {
  const { data, isLoading } = useDecisions('pending')
  const answer = useAnswerDecision()
  const [active, setActive] = useState<{ id: number; prompt: string } | null>(null)

  const decisions = data?.decisions || []

  return (
    <>
      <Card className="h-full">
        <CardHeader>
          <div className="flex items-center gap-2">
            <CardTitle>Decisions</CardTitle>
            {decisions.length > 0 && <Badge variant="red">{decisions.length}</Badge>}
          </div>
        </CardHeader>
        <CardContent>
          {isLoading && <div className="skeleton h-20 rounded-lg" />}
          {!isLoading && decisions.length === 0 && (
            <div className="flex flex-col items-center gap-2 py-8 text-text-subtle">
              <MessageSquare size={24} className="opacity-30" />
              <p className="text-sm">No pending decisions</p>
            </div>
          )}
          <div className="space-y-2 max-h-72 overflow-y-auto">
            {decisions.map(d => (
              <div key={d.id} className="rounded-lg border border-border bg-surface p-3 space-y-2">
                <p className="text-xs text-text line-clamp-3">{d.prompt}</p>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-text-subtle">{relativeTime(d.created_at)}</span>
                  <Button
                    size="sm"
                    variant="primary"
                    onClick={() => setActive({ id: d.id, prompt: d.prompt })}
                  >
                    Answer
                  </Button>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
      {active && (
        <DecisionModal
          prompt={active.prompt}
          onSubmit={ans => answer.mutate({ id: active.id, answer: ans })}
          onClose={() => setActive(null)}
        />
      )}
    </>
  )
}

// ─── Inbox ───────────────────────────────────────────────────────────────────

export function InboxCard() {
  const { data, isLoading } = useInbox()
  const markRead = useMarkRead()
  const reply = useReplyInbox()
  const [replying, setReplying] = useState<number | null>(null)
  const [replyText, setReplyText] = useState('')

  const messages = data?.messages || []

  return (
    <Card className="h-full">
      <CardHeader>
        <div className="flex items-center gap-2">
          <CardTitle>Inbox</CardTitle>
          {messages.length > 0 && <Badge variant="cyan">{messages.length} unread</Badge>}
        </div>
      </CardHeader>
      <CardContent>
        {isLoading && <div className="skeleton h-20 rounded-lg" />}
        {!isLoading && messages.length === 0 && (
          <div className="flex flex-col items-center gap-2 py-8 text-text-subtle">
            <Inbox size={24} className="opacity-30" />
            <p className="text-sm">Inbox empty</p>
          </div>
        )}
        <div className="space-y-2 max-h-72 overflow-y-auto">
          {messages.map(m => (
            <div key={m.id} className="rounded-lg border border-border bg-surface p-3 space-y-2">
              <p className="text-xs text-text">{m.body}</p>
              <div className="flex items-center justify-between gap-2">
                <span className="text-xs text-text-subtle">{relativeTime(m.created_at)}</span>
                <div className="flex gap-1">
                  <Button size="sm" variant="ghost" onClick={() => markRead.mutate(m.id)}>Mark read</Button>
                  <Button size="sm" variant="secondary" onClick={() => { setReplying(m.id); setReplyText('') }}>Reply</Button>
                </div>
              </div>
              {replying === m.id && (
                <div className="flex gap-2 mt-2">
                  <input
                    autoFocus
                    value={replyText}
                    onChange={e => setReplyText(e.target.value)}
                    onKeyDown={e => {
                      if (e.key === 'Enter') {
                        reply.mutate({ id: m.id, body: replyText })
                        setReplying(null)
                      }
                      if (e.key === 'Escape') setReplying(null)
                    }}
                    className="flex-1 bg-surface-2 border border-border rounded-md px-2 py-1 text-xs text-text outline-none focus:border-border-glow"
                    placeholder="Reply…"
                  />
                  <Button
                    size="sm"
                    variant="primary"
                    onClick={() => { reply.mutate({ id: m.id, body: replyText }); setReplying(null) }}
                  >
                    <Send size={11} />
                  </Button>
                </div>
              )}
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}
