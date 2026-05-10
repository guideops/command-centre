import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useMcpServers, useMcpServerTools, useSkills, useContextHealth } from '@/hooks/useQueries'
import { api, type Skill } from '@/lib/api'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card'
import { CollapsibleSection } from '@/components/ui/CollapsibleSection'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { fmtMs, fmtTokens } from '@/lib/utils'
import { cn } from '@/lib/utils'
import { ChevronDown, Server, Zap, CheckCircle, Code2, Settings } from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'

const fadeUp = { initial: { opacity: 0, y: 6 }, animate: { opacity: 1, y: 0 }, transition: { duration: 0.3 } }

type Range = '7d' | '30d'

// ─── MCP Server Row ───────────────────────────────────────────────────────────

function McpServerRow({ server, range }: { server: string; range: Range }) {
  const [expanded, setExpanded] = useState(false)
  const { data, isLoading } = useMcpServerTools(expanded ? server : '', range)
  const tools = data?.tools || []

  return (
    <div className="border border-border rounded-xl overflow-hidden">
      <button
        onClick={() => setExpanded(e => !e)}
        className="w-full flex items-center gap-3 px-4 py-3 hover:bg-surface-2/50 transition-colors text-left"
      >
        <Server size={14} className="text-text-dim flex-shrink-0" />
        <span className="flex-1 font-mono text-sm text-text">{server}</span>
        <motion.span animate={{ rotate: expanded ? 180 : 0 }} transition={{ duration: 0.2 }}>
          <ChevronDown size={14} className="text-text-subtle" />
        </motion.span>
      </button>

      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0 }}
            animate={{ height: 'auto' }}
            exit={{ height: 0 }}
            transition={{ duration: 0.2, ease: 'easeOut' }}
            className="overflow-hidden"
          >
            <div className="border-t border-border bg-surface-2/30 px-4 py-3">
              {isLoading ? (
                <div className="skeleton h-24 rounded-lg" />
              ) : tools.length === 0 ? (
                <p className="text-xs text-text-subtle text-center py-4">No tool data. Use OTEL_LOG_TOOL_DETAILS=1 for precise per-tool breakdown.</p>
              ) : (
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-text-subtle">
                      <th className="text-left pb-2">Tool</th>
                      <th className="text-right pb-2">p50</th>
                      <th className="text-right pb-2">p95</th>
                      <th className="text-right pb-2">max</th>
                      <th className="text-right pb-2">err%</th>
                      <th className="text-right pb-2">N</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/50">
                    {tools.map(t => (
                      <tr key={t.tool} className="hover:bg-surface/50">
                        <td className="py-1.5 font-mono text-text flex items-center gap-1">
                          {t.p95 >= 10000 && <span className="text-[10px]">· slow</span>}
                          {t.p95 < 500 && <span className="text-[10px] text-green">· fast</span>}
                          {t.tool}
                        </td>
                        <td className="py-1.5 text-right font-mono text-text-dim">{fmtMs(t.p50)}</td>
                        <td className={cn('py-1.5 text-right font-mono', t.p95 >= 10000 ? 'text-red' : t.p95 < 500 ? 'text-green' : 'text-text')}>
                          {fmtMs(t.p95)}
                        </td>
                        <td className="py-1.5 text-right font-mono text-text-subtle">{fmtMs(t.max_ms)}</td>
                        <td className={cn('py-1.5 text-right font-mono', t.error_rate > 0.1 ? 'text-red' : 'text-text-dim')}>
                          {Math.round(t.error_rate * 100)}%
                        </td>
                        <td className="py-1.5 text-right text-text-subtle">{t.calls}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

// ─── MCP Panel ────────────────────────────────────────────────────────────────

function MCPPanel() {
  const [range, setRange] = useState<Range>('7d')
  const { data, isLoading } = useMcpServers(range)
  const servers = data?.servers || []

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle>MCP Servers</CardTitle>
            <p className="text-xs text-text-dim mt-0.5">Click server to expand per-tool breakdown</p>
          </div>
          <div className="flex gap-1">
            {(['7d', '30d'] as Range[]).map(r => (
              <button
                key={r}
                onClick={() => setRange(r)}
                className={`px-2 py-1 text-xs rounded font-mono ${range === r ? 'bg-surface-2 text-text border border-border' : 'text-text-dim hover:text-text'}`}
              >
                {r}
              </button>
            ))}
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {isLoading ? <div className="skeleton h-40 rounded-lg" /> : servers.length === 0 ? (
          <div className="text-center py-12 text-text-subtle">
            <Server size={32} className="mx-auto mb-3 opacity-20" />
            <p className="text-sm">No MCP data yet</p>
            <p className="text-xs mt-1">Enable OTEL to see MCP server metrics</p>
          </div>
        ) : (
          <div className="space-y-2">
            {/* Summary table */}
            <table className="w-full text-xs mb-4">
              <thead>
                <tr className="text-text-subtle">
                  <th className="text-left pb-2">Server</th>
                  <th className="text-right pb-2">Calls</th>
                  <th className="text-right pb-2">Avg latency</th>
                  <th className="text-right pb-2">p95</th>
                  <th className="text-right pb-2">Errors</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/50">
                {servers.map(s => (
                  <tr key={s.server} className="hover:bg-surface-2/30">
                    <td className="py-2 font-mono text-text">{s.server}</td>
                    <td className="py-2 text-right font-mono text-text-dim">{s.total_calls}</td>
                    <td className="py-2 text-right font-mono text-text-dim">{fmtMs(s.avg_latency)}</td>
                    <td className={cn('py-2 text-right font-mono', s.p95 >= 10000 ? 'text-red font-semibold' : s.p95 < 500 ? 'text-green' : 'text-text')}>
                      {fmtMs(s.p95)}
                    </td>
                    <td className={cn('py-2 text-right font-mono', s.errors > 0 ? 'text-red' : 'text-text-subtle')}>
                      {s.errors}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {/* Expandable per-server rows */}
            <div className="space-y-2">
              {servers.map(s => (
                <McpServerRow key={s.server} server={s.server} range={range} />
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

// ─── Skills Registry ──────────────────────────────────────────────────────────

function SkillsRegistry() {
  const { data, isLoading } = useSkills()
  const qc = useQueryClient()
  const skills = data?.skills || []

  const updateAutonomy = async (name: string, level: string) => {
    await api.updateSkillAutonomy(name, level)
    qc.invalidateQueries({ queryKey: ['skills'] })
  }

  return (
    <Card className="col-span-2">
      <CardHeader>
        <CardTitle>Skills Registry</CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading ? <div className="skeleton h-40 rounded-lg" /> : skills.length === 0 ? (
          <div className="text-center py-8 text-text-subtle text-sm">
            <Code2 size={24} className="mx-auto mb-2 opacity-30" />
            <p>No skills found</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-text-subtle border-b border-border">
                  <th className="text-left pb-2 font-normal">Name</th>
                  <th className="text-left pb-2 font-normal">Environment</th>
                  <th className="text-left pb-2 font-normal">Description</th>
                  <th className="text-left pb-2 font-normal">Autonomy</th>
                  <th className="text-right pb-2 font-normal">Scripts</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/50">
                {skills.map(s => (
                  <tr key={s.name} className="hover:bg-surface-2/30">
                    <td className="py-2 font-mono text-text font-medium">{s.name}</td>
                    <td className="py-2">
                      <Badge variant="default">{s.environment}</Badge>
                    </td>
                    <td className="py-2 text-text-dim max-w-[240px] truncate">{s.description || '—'}</td>
                    <td className="py-2">
                      <select
                        value={s.autonomy_level}
                        onChange={e => updateAutonomy(s.name, e.target.value)}
                        className="bg-surface-2 border border-border rounded px-1.5 py-0.5 text-xs text-text outline-none"
                      >
                        <option value="auto">auto</option>
                        <option value="review">review</option>
                        <option value="manual">manual</option>
                      </select>
                    </td>
                    <td className="py-2 text-right text-text-subtle">{s.script_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

// ─── Context Health ───────────────────────────────────────────────────────────

function ContextHealthCard() {
  const { data, isLoading } = useContextHealth()

  const checks = [
    { label: 'settings.json', ok: data?.settings_exists, detail: data?.settings_size_bytes ? `${(data.settings_size_bytes / 1024).toFixed(1)}KB` : undefined },
    { label: 'CLAUDE.md', ok: data?.claude_md_exists, detail: data?.claude_md_lines ? `${data.claude_md_lines} lines` : undefined },
    { label: 'MCP servers', ok: (data?.mcp_server_count || 0) > 0, detail: data?.mcp_server_count != null ? `${data.mcp_server_count}` : undefined },
    { label: 'Hooks', ok: (data?.hook_count || 0) >= 0, detail: data?.hook_count != null ? `${data.hook_count}` : undefined },
  ]

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <Settings size={14} className="text-text-dim" />
          <CardTitle>Context Health</CardTitle>
        </div>
      </CardHeader>
      <CardContent>
        {isLoading ? <div className="skeleton h-24 rounded-lg" /> : (
          <div className="space-y-2">
            {checks.map((c, i) => (
              <div key={i} className="flex items-center gap-2 text-xs">
                <CheckCircle size={12} className={c.ok ? 'text-green' : 'text-text-subtle'} />
                <span className="text-text-dim">{c.label}</span>
                {c.detail && <span className="ml-auto font-mono text-text-subtle">{c.detail}</span>}
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

export function SkillsPage() {
  return (
    <motion.div {...fadeUp} className="space-y-4">
      <CollapsibleSection id="mcp-servers" title="MCP Servers" defaultOpen>
        <MCPPanel />
      </CollapsibleSection>

      <CollapsibleSection id="skills-registry" title="Skills & Context" defaultOpen>
        <div className="grid grid-cols-3 gap-4">
          <ContextHealthCard />
          <SkillsRegistry />
        </div>
      </CollapsibleSection>
    </motion.div>
  )
}
