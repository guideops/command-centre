import { ReactNode, useState, useEffect } from 'react'
import { Link, useRouterState } from '@tanstack/react-router'
import { LayoutDashboard, Activity, Puzzle, Terminal, Zap } from 'lucide-react'
import { cn } from '@/lib/utils'
import { CommandPalette } from './CommandPalette'

const NAV = [
  { to: '/', label: 'Command', icon: LayoutDashboard },
  { to: '/activity', label: 'Activity', icon: Activity },
  { to: '/skills', label: 'Skills & MCP', icon: Puzzle },
]

export function AppShell({ children }: { children: ReactNode }) {
  const [cmdOpen, setCmdOpen] = useState(false)
  const router = useRouterState()

  useEffect(() => {
    const handle = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault()
        setCmdOpen(true)
      }
    }
    window.addEventListener('keydown', handle)
    return () => window.removeEventListener('keydown', handle)
  }, [])

  return (
    <div className="min-h-screen flex flex-col">
      <header className="sticky top-0 z-30 border-b border-border bg-surface/80 backdrop-blur-md flex-shrink-0">
        <div className="max-w-screen-2xl mx-auto px-6 h-12 flex items-center gap-6">
          <div className="flex items-center gap-2 mr-4">
            <div className="w-6 h-6 rounded-md bg-accent-gradient flex items-center justify-center">
              <Terminal size={12} className="text-white" />
            </div>
            <span className="text-sm font-semibold gradient-text">Command Centre</span>
          </div>

          <nav className="flex items-center gap-1">
            {NAV.map(({ to, label, icon: Icon }) => {
              const active = router.location.pathname === to
              return (
                <Link
                  key={to}
                  to={to}
                  className={cn(
                    'flex items-center gap-1.5 px-3 h-8 rounded-md text-xs font-medium transition-all duration-150',
                    active
                      ? 'bg-surface-2 text-text border border-border'
                      : 'text-text-dim hover:text-text hover:bg-surface-2/50'
                  )}
                >
                  <Icon size={13} />
                  {label}
                </Link>
              )
            })}
          </nav>

          <div className="ml-auto">
            <button
              onClick={() => setCmdOpen(true)}
              className="flex items-center gap-2 px-3 h-7 rounded-md text-xs text-text-subtle border border-border hover:border-border-glow hover:text-text-dim transition-all duration-150 bg-surface"
            >
              <Zap size={11} />
              <span>Quick action</span>
              <kbd className="ml-1 font-mono text-[10px] bg-surface-2 px-1 py-0.5 rounded border border-border">⌘K</kbd>
            </button>
          </div>
        </div>
      </header>

      <main className="flex-1 max-w-screen-2xl mx-auto w-full px-6 py-6">
        {children}
      </main>

      <CommandPalette open={cmdOpen} onClose={() => setCmdOpen(false)} />
    </div>
  )
}
