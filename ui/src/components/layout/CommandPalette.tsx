import { useState, useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { Search, LayoutDashboard, Activity, Puzzle, Plus } from 'lucide-react'
import { useNavigate } from '@tanstack/react-router'
import { cn } from '@/lib/utils'

interface CommandPaletteProps {
  open: boolean
  onClose: () => void
}

const COMMANDS = [
  { id: 'home', label: 'Go to Command', icon: LayoutDashboard, action: 'nav', target: '/' },
  { id: 'activity', label: 'Go to Activity', icon: Activity, action: 'nav', target: '/activity' },
  { id: 'skills', label: 'Go to Skills & MCP', icon: Puzzle, action: 'nav', target: '/skills' },
  { id: 'new-task', label: 'Queue a Task', icon: Plus, action: 'task', target: '' },
]

export function CommandPalette({ open, onClose }: CommandPaletteProps) {
  const [query, setQuery] = useState('')
  const [idx, setIdx] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)
  const navigate = useNavigate()

  useEffect(() => {
    if (open) {
      setQuery('')
      setIdx(0)
      setTimeout(() => inputRef.current?.focus(), 50)
    }
  }, [open])

  useEffect(() => {
    if (!open) return
    const handle = (e: KeyboardEvent) => {
      if (e.key === 'Escape') { onClose(); return }
      if (e.key === 'ArrowDown') { setIdx(i => Math.min(i + 1, filtered.length - 1)); e.preventDefault() }
      if (e.key === 'ArrowUp') { setIdx(i => Math.max(i - 1, 0)); e.preventDefault() }
      if (e.key === 'Enter') { runCmd(filtered[idx]); e.preventDefault() }
    }
    window.addEventListener('keydown', handle)
    return () => window.removeEventListener('keydown', handle)
  }, [open, idx, query])

  const filtered = COMMANDS.filter(c => !query || c.label.toLowerCase().includes(query.toLowerCase()))

  function runCmd(cmd: (typeof COMMANDS)[0] | undefined) {
    if (!cmd) return
    onClose()
    if (cmd.action === 'nav') navigate({ to: cmd.target as '/' | '/activity' | '/skills' })
  }

  return createPortal(
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
          />
          <motion.div
            className="fixed top-[20vh] left-1/2 -translate-x-1/2 z-50 w-full max-w-[560px] rounded-xl border border-border bg-surface shadow-2xl shadow-black/50 overflow-hidden"
            initial={{ opacity: 0, y: -8, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -8, scale: 0.97 }}
            transition={{ duration: 0.15 }}
          >
            <div className="flex items-center gap-3 px-4 py-3 border-b border-border">
              <Search size={15} className="text-text-subtle flex-shrink-0" />
              <input
                ref={inputRef}
                value={query}
                onChange={e => { setQuery(e.target.value); setIdx(0) }}
                placeholder="Search commands…"
                className="flex-1 bg-transparent text-sm text-text placeholder:text-text-subtle outline-none"
              />
            </div>
            <div className="py-2 max-h-[320px] overflow-y-auto">
              {filtered.length === 0 && (
                <p className="px-4 py-3 text-xs text-text-subtle">No results</p>
              )}
              {filtered.map((cmd, i) => (
                <button
                  key={cmd.id}
                  onClick={() => runCmd(cmd)}
                  className={cn(
                    'flex w-full items-center gap-3 px-4 py-2.5 text-sm transition-colors',
                    i === idx ? 'bg-surface-2 text-text' : 'text-text-dim hover:bg-surface-2/50 hover:text-text'
                  )}
                >
                  <cmd.icon size={14} className="flex-shrink-0" />
                  {cmd.label}
                </button>
              ))}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>,
    document.body
  )
}
