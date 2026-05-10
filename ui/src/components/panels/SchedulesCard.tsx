import { useState } from 'react'
import { useSchedules, useCreateSchedule, useUpdateSchedule, useDeleteSchedule, useSkills } from '@/hooks/useQueries'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Sheet } from '@/components/ui/Sheet'
import { relativeTime } from '@/lib/utils'
import { api, type CreateScheduleInput } from '@/lib/api'
import { Plus, Trash2, Clock, AlertCircle } from 'lucide-react'
import { cn } from '@/lib/utils'

const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
const MINUTES = [0, 15, 30, 45]

function buildCron(hour: number, minute: number, days: number[]): string {
  if (days.length === 7) return `${minute} ${hour} * * *`
  if (days.length === 0) return `${minute} ${hour} * * *`
  const dayStr = days.sort().join(',')
  return `${minute} ${hour} * * ${dayStr}`
}

function ScheduleComposer({ open, onClose }: { open: boolean; onClose: () => void }) {
  const create = useCreateSchedule()
  const { data: skillsData } = useSkills()
  const skills = skillsData?.skills || []

  const [name, setName] = useState('')
  const [taskTitle, setTaskTitle] = useState('')
  const [taskDesc, setTaskDesc] = useState('')
  const [skill, setSkill] = useState('')
  const [hour, setHour] = useState(9)
  const [minute, setMinute] = useState(0)
  const [selectedDays, setSelectedDays] = useState<number[]>([0, 1, 2, 3, 4])
  const [enabled, setEnabled] = useState(true)
  const [nlText, setNlText] = useState('')
  const [parsedCron, setParsedCron] = useState<string | null>(null)
  const [parsing, setParsing] = useState(false)

  const derivedCron = parsedCron || buildCron(hour, minute, selectedDays)
  const toggleDay = (d: number) => setSelectedDays(prev => prev.includes(d) ? prev.filter(x => x !== d) : [...prev, d])

  const parseNl = async () => {
    if (!nlText) return
    setParsing(true)
    try {
      const res = await api.parseNlSchedule(nlText)
      setParsedCron(res.cron)
    } finally {
      setParsing(false)
    }
  }

  const submit = () => {
    if (!name || !taskTitle) return
    create.mutate({
      name, cron_expression: derivedCron, task_title: taskTitle,
      task_description: taskDesc || undefined,
      assigned_skill: skill || undefined, enabled,
    }, { onSuccess: onClose })
  }

  return (
    <Sheet open={open} onClose={onClose} title="New Schedule" width="w-[520px]">
      <div className="space-y-4">
        <div>
          <label className="kicker block mb-1">Schedule name *</label>
          <input
            autoFocus
            value={name}
            onChange={e => setName(e.target.value)}
            className="w-full bg-surface-2 border border-border rounded-lg px-3 py-2 text-sm text-text outline-none focus:border-border-glow"
            placeholder="Daily standup prep…"
          />
        </div>

        <div>
          <label className="kicker block mb-1">Natural language (optional)</label>
          <div className="flex gap-2">
            <input
              value={nlText}
              onChange={e => setNlText(e.target.value)}
              className="flex-1 bg-surface-2 border border-border rounded-lg px-3 py-2 text-sm text-text outline-none focus:border-border-glow"
              placeholder="Every weekday at 9am…"
            />
            <Button size="sm" variant="secondary" onClick={parseNl} disabled={parsing}>
              {parsing ? '…' : 'Parse'}
            </Button>
          </div>
        </div>

        <div className="rounded-lg border border-border bg-surface-2 p-3 space-y-3">
          <div className="flex gap-3">
            <div>
              <label className="kicker block mb-1">Hour (0-23)</label>
              <input
                type="number" min={0} max={23} value={hour}
                onChange={e => { setHour(Number(e.target.value)); setParsedCron(null) }}
                className="w-20 bg-surface border border-border rounded-lg px-2 py-1.5 text-sm text-text outline-none font-mono"
              />
            </div>
            <div>
              <label className="kicker block mb-1">Minute</label>
              <select
                value={minute}
                onChange={e => { setMinute(Number(e.target.value)); setParsedCron(null) }}
                className="w-20 bg-surface border border-border rounded-lg px-2 py-1.5 text-sm text-text outline-none"
              >
                {MINUTES.map(m => <option key={m} value={m}>{String(m).padStart(2, '0')}</option>)}
              </select>
            </div>
          </div>

          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="kicker">Days</label>
              <div className="flex gap-1 text-xs">
                <button className="text-text-dim hover:text-text" onClick={() => { setSelectedDays([0,1,2,3,4,5,6]); setParsedCron(null) }}>Every day</button>
                <span className="text-text-subtle">·</span>
                <button className="text-text-dim hover:text-text" onClick={() => { setSelectedDays([0,1,2,3,4]); setParsedCron(null) }}>Weekdays</button>
                <span className="text-text-subtle">·</span>
                <button className="text-text-dim hover:text-text" onClick={() => { setSelectedDays([5,6]); setParsedCron(null) }}>Weekends</button>
              </div>
            </div>
            <div className="flex gap-1">
              {DAYS.map((d, i) => (
                <button
                  key={d}
                  onClick={() => { toggleDay(i); setParsedCron(null) }}
                  className={cn('flex-1 py-1 text-xs rounded-md transition-colors', selectedDays.includes(i) ? 'bg-accent/20 border border-accent/40 text-accent' : 'bg-surface border border-border text-text-dim')}
                >
                  {d}
                </button>
              ))}
            </div>
          </div>

          <div className="font-mono text-xs text-text-dim">
            Cron: <span className="text-cyan">{derivedCron}</span>
          </div>
        </div>

        <div>
          <label className="kicker block mb-1">Task title *</label>
          <input
            value={taskTitle}
            onChange={e => setTaskTitle(e.target.value)}
            className="w-full bg-surface-2 border border-border rounded-lg px-3 py-2 text-sm text-text outline-none focus:border-border-glow"
            placeholder="What should Claude do?"
          />
        </div>

        <div>
          <label className="kicker block mb-1">Task details</label>
          <textarea
            value={taskDesc}
            onChange={e => setTaskDesc(e.target.value)}
            rows={3}
            className="w-full bg-surface-2 border border-border rounded-lg px-3 py-2 text-sm text-text outline-none focus:border-border-glow resize-none"
          />
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="kicker block mb-1">Skill</label>
            <select
              value={skill}
              onChange={e => setSkill(e.target.value)}
              className="w-full bg-surface-2 border border-border rounded-lg px-3 py-2 text-xs text-text outline-none"
            >
              <option value="">None</option>
              {skills.map(s => <option key={s.name} value={s.name}>{s.name}</option>)}
            </select>
          </div>
          <div className="flex items-end">
            <label className="flex items-center gap-2 text-sm text-text-dim cursor-pointer">
              <input
                type="checkbox"
                checked={enabled}
                onChange={e => setEnabled(e.target.checked)}
                className="rounded border-border"
              />
              Enabled
            </label>
          </div>
        </div>

        <div className="flex gap-2 justify-end pt-2 border-t border-border">
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button variant="primary" onClick={submit} disabled={!name || !taskTitle || create.isPending}>
            <Plus size={14} /> Create Schedule
          </Button>
        </div>
      </div>
    </Sheet>
  )
}

export function SchedulesCard() {
  const { data, isLoading } = useSchedules()
  const update = useUpdateSchedule()
  const del = useDeleteSchedule()
  const [composerOpen, setComposerOpen] = useState(false)

  const schedules = data?.schedules || []
  const now = new Date()

  return (
    <>
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Schedules</CardTitle>
              <p className="text-xs text-text-dim mt-0.5">TZ: {Intl.DateTimeFormat().resolvedOptions().timeZone}</p>
            </div>
            <Button variant="primary" size="sm" onClick={() => setComposerOpen(true)}>
              <Plus size={13} /> New Schedule
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {isLoading ? <div className="skeleton h-32 rounded-lg" /> : schedules.length === 0 ? (
            <div className="text-center py-8 text-text-subtle text-sm flex flex-col items-center gap-2">
              <Clock size={24} className="opacity-30" />
              <p>No schedules yet</p>
            </div>
          ) : (
            <div className="space-y-2">
              {schedules.map(s => {
                const nextRun = s.next_run_at ? new Date(s.next_run_at) : null
                const overdue = nextRun && nextRun < now && new Date(now.getTime() - 5 * 60 * 1000) > nextRun
                return (
                  <div key={s.id} className="rounded-lg border border-border bg-surface p-3 space-y-2">
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-2 min-w-0">
                        {overdue && <AlertCircle size={13} className="text-amber flex-shrink-0" />}
                        <span className="text-sm font-medium text-text truncate">{s.name}</span>
                      </div>
                      <div className="flex items-center gap-1.5 flex-shrink-0">
                        <button
                          onClick={() => update.mutate({ id: s.id, data: { enabled: s.enabled ? 0 : 1 } })}
                          className={cn('relative w-8 h-4 rounded-full transition-colors', s.enabled ? 'bg-green/60' : 'bg-surface-2 border border-border')}
                        >
                          <span className={cn('absolute top-0.5 w-3 h-3 rounded-full bg-white transition-transform', s.enabled ? 'translate-x-4' : 'translate-x-0.5')} />
                        </button>
                        <Button size="sm" variant="ghost" onClick={() => del.mutate(s.id)}>
                          <Trash2 size={11} />
                        </Button>
                      </div>
                    </div>
                    <div className="flex flex-wrap gap-2 text-xs text-text-dim">
                      <span className="font-mono text-text-subtle">{s.cron_expression}</span>
                      {nextRun && <span className={overdue ? 'text-amber' : ''}>Next: {relativeTime(s.next_run_at)}</span>}
                      {s.last_run_at && <span>Last: {relativeTime(s.last_run_at)}</span>}
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </CardContent>
      </Card>
      <ScheduleComposer open={composerOpen} onClose={() => setComposerOpen(false)} />
    </>
  )
}
