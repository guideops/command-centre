import { useSummary } from '@/hooks/useQueries'
import { fmtTokens } from '@/lib/utils'
import { MessageSquare, Zap, Wrench, AlertTriangle, type LucideIcon } from 'lucide-react'

function KpiTile({ label, value, icon: Icon, color }: {
  label: string; value: string; icon: LucideIcon; color: string
}) {
  return (
    <div className="flex-1 rounded-xl border border-border bg-surface p-4 min-w-[120px]">
      <div className={`inline-flex p-2 rounded-lg mb-3 ${color}`}>
        <Icon size={16} />
      </div>
      <div className="text-2xl font-bold font-mono text-text tracking-tight">{value}</div>
      <div className="text-xs text-text-dim mt-1">{label}</div>
    </div>
  )
}

export function KpiRow() {
  const { data, isLoading } = useSummary()

  if (isLoading) {
    return (
      <div className="flex gap-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="flex-1 rounded-xl border border-border bg-surface p-4 h-28">
            <div className="skeleton h-4 w-8 rounded mb-3" />
            <div className="skeleton h-8 w-20 rounded mb-2" />
            <div className="skeleton h-3 w-16 rounded" />
          </div>
        ))}
      </div>
    )
  }

  if (!data) return null

  return (
    <div className="flex gap-4">
      <KpiTile label="Sessions today" value={String(data.sessions_today)} icon={MessageSquare} color="bg-accent/10 text-accent" />
      <KpiTile label="Tokens today" value={fmtTokens(data.tokens_today)} icon={Zap} color="bg-cyan/10 text-cyan" />
      <KpiTile label="Tool calls today" value={fmtTokens(data.tools_today)} icon={Wrench} color="bg-green/10 text-green" />
      <KpiTile label="Errors today" value={String(data.errors_today)} icon={AlertTriangle} color={data.errors_today > 0 ? "bg-red/10 text-red" : "bg-green/10 text-green"} />
    </div>
  )
}
