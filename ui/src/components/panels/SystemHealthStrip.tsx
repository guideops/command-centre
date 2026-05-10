import { useHealth } from '@/hooks/useQueries'
import { secondsToHuman } from '@/lib/utils'
import { cn } from '@/lib/utils'

function HealthPill({ label, value, ok }: { label: string; value: string; ok: boolean }) {
  return (
    <div className={cn(
      'flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-mono border',
      ok
        ? 'border-green/20 bg-green/5 text-green'
        : 'border-red/20 bg-red/5 text-red'
    )}>
      <span className={cn('w-1.5 h-1.5 rounded-full flex-shrink-0', ok ? 'bg-green' : 'bg-red animate-pulse')} />
      <span className="text-text-subtle">{label}</span>
      <span className="font-medium">{value}</span>
    </div>
  )
}

export function SystemHealthStrip() {
  const { data, isLoading } = useHealth()

  if (isLoading) {
    return (
      <div className="flex gap-2 py-2">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="skeleton h-7 w-28 rounded-md" />
        ))}
      </div>
    )
  }

  if (!data) return null

  const otelAge = data.last_otel_age_s
  const daemonAge = data.daemon_age_s

  return (
    <div className="flex flex-wrap gap-2 py-2">
      <HealthPill label="uptime" value={secondsToHuman(data.uptime_s)} ok={true} />
      <HealthPill label="mem" value={`${data.memory_mb.toFixed(0)}MB`} ok={data.memory_mb < 500} />
      <HealthPill
        label="otel"
        value={otelAge == null ? 'none' : otelAge < 60 ? `${Math.round(otelAge)}s ago` : `${Math.floor(otelAge / 60)}m ago`}
        ok={otelAge == null || otelAge < 120}
      />
      <HealthPill
        label="daemon"
        value={daemonAge == null ? 'none' : `${Math.floor(daemonAge / 60)}m ago`}
        ok={daemonAge == null || daemonAge < 300}
      />
      <HealthPill label="tz" value={data.tzname} ok={true} />
    </div>
  )
}
