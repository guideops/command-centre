import { cn } from '@/lib/utils'
import { HTMLAttributes } from 'react'

type BadgeVariant = 'default' | 'green' | 'amber' | 'red' | 'cyan' | 'purple' | 'muted'

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant
}

const variantMap: Record<BadgeVariant, string> = {
  default: 'bg-surface-2 border border-border text-text-dim',
  green: 'bg-green/10 border border-green/30 text-green',
  amber: 'bg-amber/10 border border-amber/30 text-amber',
  red: 'bg-red/10 border border-red/30 text-red',
  cyan: 'bg-cyan/10 border border-cyan/30 text-cyan',
  purple: 'bg-accent-2/10 border border-accent-2/30 text-accent-2',
  muted: 'bg-transparent text-text-subtle border border-transparent',
}

export function Badge({ className, variant = 'default', ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-md px-1.5 py-0.5 text-xs font-medium font-mono',
        variantMap[variant],
        className
      )}
      {...props}
    />
  )
}

export function StatePill({ state }: { state: string }) {
  const map: Record<string, { label: string; variant: BadgeVariant }> = {
    running: { label: 'running', variant: 'cyan' },
    pending: { label: 'pending', variant: 'amber' },
    done: { label: 'done', variant: 'green' },
    failed: { label: 'failed', variant: 'red' },
    awaiting_approval: { label: 'approval', variant: 'purple' },
    cancelled: { label: 'cancelled', variant: 'muted' },
    stopped: { label: 'stopped', variant: 'muted' },
    waiting: { label: 'waiting', variant: 'amber' },
  }
  const config = map[state] || { label: state, variant: 'default' as BadgeVariant }
  return <Badge variant={config.variant}>{config.label}</Badge>
}
