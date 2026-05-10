import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'
import { formatDistanceToNow, format, parseISO } from 'date-fns'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function relativeTime(ts: string | null | undefined): string {
  if (!ts) return '—'
  try {
    const dt = parseISO(ts)
    return formatDistanceToNow(dt, { addSuffix: true })
  } catch {
    return ts
  }
}

export function absoluteTime(ts: string | null | undefined): string {
  if (!ts) return '—'
  try {
    return format(parseISO(ts), 'MMM d, yyyy HH:mm:ss')
  } catch {
    return ts
  }
}

export function fmtTokens(n: number | null | undefined): string {
  if (n == null) return '—'
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`
  return String(n)
}

export function fmtMs(ms: number | null | undefined): string {
  if (ms == null) return '—'
  if (ms >= 60_000) return `${(ms / 60_000).toFixed(1)}m`
  if (ms >= 1_000) return `${(ms / 1_000).toFixed(1)}s`
  return `${ms}ms`
}

export function fmtCost(usd: number | null | undefined): string {
  if (usd == null) return '—'
  return `$${usd.toFixed(4)}`
}

export function projectName(cwd: string | null | undefined): string {
  if (!cwd) return 'Unknown'
  const normalized = cwd.replace(/\\/g, '/').replace(/^\/[Uu]sers\/[^/]+/, '~').replace(/^[A-Z]:/, '')
  const parts = normalized.split('/')
  return parts[parts.length - 1] || normalized
}

export function secondsToHuman(s: number): string {
  if (s < 60) return `${s}s`
  if (s < 3600) return `${Math.floor(s / 60)}m ${s % 60}s`
  return `${Math.floor(s / 3600)}h ${Math.floor((s % 3600) / 60)}m`
}
