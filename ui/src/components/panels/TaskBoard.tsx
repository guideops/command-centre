import { useState } from 'react'
import { useTasks, useCreateTask, useApproveTask, useRerunTask, useDeleteTask, useSkills } from '@/hooks/useQueries'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge, StatePill } from '@/components/ui/Badge'
import { Sheet } from '@/components/ui/Sheet'
import { relativeTime, fmtMs } from '@/lib/utils'
import type { Task, CreateTaskInput, Skill } from '@/lib/api'
import { Plus, Play, RotateCcw, Trash2, CheckCircle } from 'lucide-react'
import { cn } from '@/lib/utils'

const RISK_COLORS: Record<string, string> = {
  low: 'text-green',
  medium: 'text-amber',
  high: 'text-red',
}

const QUADRANT_DOTS: Record<string, string> = {
  do: 'bg-green',
  schedule: 'bg-cyan',
  delegate: 'bg-accent',
  archive: 'bg-text-subtle',
}

function TaskCard({ task }: { task: Task }) {
  const approve = useApproveTask()
  const rerun = useRerunTask()
  const del = useDeleteTask()

  return (
    <div className="rounded-lg border border-border bg-surface p-3 space-y-2 hover:border-border-glow transition-all">
      <div className="flex items-start gap-2">
        <span className={cn('w-2 h-2 rounded-full flex-shrink-0 mt-1', QUADRANT_DOTS[task.quadrant] || 'bg-text-subtle')} />
        <div className="flex-1 min-w-0">
          <p className="text-xs font-medium text-text leading-snug">{task.title}</p>
          {task.description && (
            <p className="text-xs text-text-dim mt-0.5 line-clamp-2">{task.description}</p>
          )}
        </div>
      </div>
      <div className="flex flex-wrap gap-1">
        <StatePill state={task.status} />
        {task.assigned_skill && <Badge variant="default">{task.assigned_skill}</Badge>}
        {task.model && <Badge variant="muted">{task.model.split('/').pop()?.split('-').slice(-2).join('-')}</Badge>}
        {task.risk_level !== 'low' && (
          <span className={cn('text-xs font-mono', RISK_COLORS[task.risk_level])}>{task.risk_level} risk</span>
        )}
        {task.dry_run === 1 && <Badge variant="amber">dry-run</Badge>}
      </div>
      {(task.output_summary || task.error_message) && (
        <p className={cn('text-xs p-2 rounded-md border line-clamp-2',
          task.error_message
            ? 'border-red/20 bg-red/5 text-red/80'
            : 'border-border bg-surface-2 text-text-dim'
        )}>
          {task.error_message || task.output_summary}
        </p>
      )}
      <div className="flex items-center justify-between">
        <span className="text-xs text-text-subtle">{relativeTime(task.created_at)}</span>
        <div className="flex gap-1">
          {task.status === 'awaiting_approval' && (
            <Button size="sm" variant="primary" onClick={() => approve.mutate(task.id)}>
              <CheckCircle size={11} /> Approve
            </Button>
          )}
          {task.status === 'failed' && (
            <Button size="sm" variant="secondary" onClick={() => rerun.mutate(task.id)}>
              <RotateCcw size={11} /> Rerun
            </Button>
          )}
          <Button size="sm" variant="ghost" onClick={() => del.mutate(task.id)}>
            <Trash2 size={11} />
          </Button>
        </div>
      </div>
    </div>
  )
}

function TaskComposer({ open, onClose, skills }: { open: boolean; onClose: () => void; skills: Skill[] }) {
  const create = useCreateTask()
  const [form, setForm] = useState<Partial<CreateTaskInput>>({
    execution_mode: 'stream',
    quadrant: 'do',
    risk_level: 'low',
  })

  const set = (k: keyof CreateTaskInput, v: unknown) => setForm(f => ({ ...f, [k]: v }))

  const submit = () => {
    if (!form.title) return
    create.mutate(form as CreateTaskInput, { onSuccess: () => { onClose(); setForm({ execution_mode: 'stream', quadrant: 'do', risk_level: 'low' }) } })
  }

  return (
    <Sheet open={open} onClose={onClose} title="Queue a Task" width="w-[500px]">
      <div className="space-y-4">
        <div>
          <label className="kicker block mb-1">Title *</label>
          <input
            autoFocus
            value={form.title || ''}
            onChange={e => set('title', e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') submit() }}
            className="w-full bg-surface-2 border border-border rounded-lg px-3 py-2 text-sm text-text outline-none focus:border-border-glow"
            placeholder="What should Claude do?"
          />
        </div>

        <div>
          <label className="kicker block mb-1">Description</label>
          <textarea
            value={form.description || ''}
            onChange={e => set('description', e.target.value)}
            rows={4}
            className="w-full bg-surface-2 border border-border rounded-lg px-3 py-2 text-sm text-text outline-none focus:border-border-glow resize-none"
            placeholder="Context, constraints, expected output…"
          />
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="kicker block mb-1">Mode</label>
            <select
              value={form.execution_mode || 'stream'}
              onChange={e => set('execution_mode', e.target.value)}
              className="w-full bg-surface-2 border border-border rounded-lg px-3 py-2 text-xs text-text outline-none"
            >
              <option value="stream">Interactive — reply mid-run</option>
              <option value="classic">One-shot — fire and forget</option>
            </select>
          </div>
          <div>
            <label className="kicker block mb-1">Quadrant</label>
            <select
              value={form.quadrant || 'do'}
              onChange={e => set('quadrant', e.target.value)}
              className="w-full bg-surface-2 border border-border rounded-lg px-3 py-2 text-xs text-text outline-none"
            >
              <option value="do">Do now</option>
              <option value="schedule">Schedule</option>
              <option value="delegate">Delegate</option>
              <option value="archive">Archive</option>
            </select>
          </div>
          <div>
            <label className="kicker block mb-1">Risk level</label>
            <select
              value={form.risk_level || 'low'}
              onChange={e => set('risk_level', e.target.value)}
              className="w-full bg-surface-2 border border-border rounded-lg px-3 py-2 text-xs text-text outline-none"
            >
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
            </select>
          </div>
          <div>
            <label className="kicker block mb-1">Skill</label>
            <select
              value={form.assigned_skill || ''}
              onChange={e => set('assigned_skill', e.target.value || undefined)}
              className="w-full bg-surface-2 border border-border rounded-lg px-3 py-2 text-xs text-text outline-none"
            >
              <option value="">Auto-pick</option>
              {skills.map(s => <option key={s.name} value={s.name}>{s.name}</option>)}
            </select>
          </div>
        </div>

        <div>
          <label className="kicker block mb-1">Model</label>
          <select
            value={form.model || ''}
            onChange={e => set('model', e.target.value || undefined)}
            className="w-full bg-surface-2 border border-border rounded-lg px-3 py-2 text-xs text-text outline-none"
          >
            <option value="">Default (from skill or env)</option>
            <option value="claude-opus-4-7">claude-opus-4-7</option>
            <option value="claude-sonnet-4-6">claude-sonnet-4-6</option>
            <option value="claude-haiku-4-5-20251001">claude-haiku-4-5</option>
          </select>
        </div>

        <div className="flex gap-4">
          <label className="flex items-center gap-2 text-xs text-text-dim cursor-pointer">
            <input
              type="checkbox"
              checked={!!form.requires_approval}
              onChange={e => set('requires_approval', e.target.checked)}
              className="rounded border-border"
            />
            Requires approval
          </label>
          <label className="flex items-center gap-2 text-xs text-text-dim cursor-pointer" title="Describe what would be done but don't make changes">
            <input
              type="checkbox"
              checked={!!form.dry_run}
              onChange={e => set('dry_run', e.target.checked)}
              className="rounded border-border"
            />
            Dry run
          </label>
        </div>

        <div className="flex gap-2 justify-end pt-2 border-t border-border">
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button variant="primary" onClick={submit} disabled={!form.title || create.isPending}>
            <Plus size={14} /> Queue Task
          </Button>
        </div>
      </div>
    </Sheet>
  )
}

export function TaskBoard() {
  const { data, isLoading } = useTasks()
  const { data: skillsData } = useSkills()
  const [composerOpen, setComposerOpen] = useState(false)

  const tasks = data?.tasks || []
  const skills = skillsData?.skills || []

  const pending = tasks.filter(t => ['pending', 'awaiting_approval'].includes(t.status))
  const running = tasks.filter(t => t.status === 'running')
  const done = tasks.filter(t => ['done', 'failed', 'cancelled'].includes(t.status)).slice(0, 20)

  const Column = ({ title, items, color }: { title: string; items: Task[]; color: string }) => (
    <div className="flex-1 min-w-0">
      <div className="flex items-center gap-2 mb-3">
        <span className={cn('w-2 h-2 rounded-full', color)} />
        <span className="kicker">{title}</span>
        <span className="text-xs text-text-subtle">{items.length}</span>
      </div>
      <div className="space-y-2 max-h-[600px] overflow-y-auto pr-1">
        {items.map(t => <TaskCard key={t.id} task={t} />)}
        {items.length === 0 && (
          <div className="text-center py-6 text-text-subtle text-xs border border-dashed border-border rounded-lg">
            {title === 'Pending' ? 'Queue a task to get started' : 'None'}
          </div>
        )}
      </div>
    </div>
  )

  return (
    <>
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>Task Board</CardTitle>
            <Button variant="primary" size="sm" onClick={() => setComposerOpen(true)}>
              <Plus size={13} /> Queue Task
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {isLoading ? <div className="skeleton h-48 rounded-lg" /> : (
            <div className="flex gap-6">
              <Column title="Pending" items={pending} color="bg-amber" />
              <Column title="Running" items={running} color="bg-cyan animate-pulse" />
              <Column title="Done" items={done} color="bg-text-subtle" />
            </div>
          )}
        </CardContent>
      </Card>
      <TaskComposer open={composerOpen} onClose={() => setComposerOpen(false)} skills={skills} />
    </>
  )
}
