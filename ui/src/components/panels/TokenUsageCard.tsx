import { useState } from 'react'
import { useTokenUsage } from '@/hooks/useQueries'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card'
import { fmtTokens } from '@/lib/utils'

type Range = 'today' | '7d' | '30d'

const COLORS = {
  input: '#4d7cff',
  output: '#8b5cf6',
  cache_read: '#10b981',
  cache_create: '#06b6d4',
}

export function TokenUsageCard() {
  const [range, setRange] = useState<Range>('7d')
  const { data, isLoading } = useTokenUsage(range)

  const dailyMap = new Map<string, Record<string, number>>()
  data?.data.forEach(r => {
    const d = dailyMap.get(r.date) || { input: 0, output: 0, cache_read: 0, cache_create: 0 }
    d.input += r.input_tokens
    d.output += r.output_tokens
    d.cache_read += r.cache_read_tokens
    d.cache_create += r.cache_create_tokens
    dailyMap.set(r.date, d)
  })
  const days = Array.from(dailyMap.entries()).sort(([a], [b]) => a.localeCompare(b))
  const maxTotal = Math.max(...days.map(([, d]) => d.input + d.output + d.cache_read + d.cache_create), 1)

  const totals = data?.totals

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>Token Usage</CardTitle>
          <div className="flex gap-1">
            {(['today', '7d', '30d'] as Range[]).map(r => (
              <button
                key={r}
                onClick={() => setRange(r)}
                className={`px-2 py-1 text-xs rounded-md font-mono transition-colors ${range === r ? 'bg-surface-2 text-text border border-border' : 'text-text-dim hover:text-text'}`}
              >
                {r}
              </button>
            ))}
          </div>
        </div>
        {totals && (
          <div className="flex gap-4 mt-2">
            {Object.entries(COLORS).map(([key, color]) => (
              <div key={key} className="flex items-center gap-1.5 text-xs">
                <span className="w-2 h-2 rounded-sm" style={{ background: color }} />
                <span className="text-text-dim">{key.replace('_', '-')}</span>
                <span className="text-text font-mono">{fmtTokens((totals as any)[key])}</span>
              </div>
            ))}
          </div>
        )}
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="skeleton h-40 rounded-lg" />
        ) : days.length === 0 ? (
          <div className="flex items-center justify-center h-40 text-text-subtle text-sm">No token data yet</div>
        ) : (
          <div className="flex items-end gap-1 h-40">
            {days.map(([date, d]) => {
              const total = d.input + d.output + d.cache_read + d.cache_create
              const pct = total / maxTotal
              return (
                <div key={date} className="flex-1 flex flex-col justify-end gap-0 min-w-0 group" title={`${date}: ${fmtTokens(total)}`}>
                  {(['cache_create', 'cache_read', 'output', 'input'] as const).map(key => {
                    const h = pct > 0 ? (d[key] / maxTotal) * 160 : 0
                    return h > 0 ? (
                      <div
                        key={key}
                        style={{ height: `${h}px`, background: COLORS[key] }}
                        className="w-full transition-opacity group-hover:opacity-80 first:rounded-t-sm"
                      />
                    ) : null
                  })}
                </div>
              )
            })}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
