import { useState, useEffect, ReactNode, useId } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { ChevronRight } from 'lucide-react'
import { cn } from '@/lib/utils'

interface CollapsibleSectionProps {
  id: string
  title: string
  subtitle?: string
  summary?: ReactNode
  defaultOpen?: boolean
  children: ReactNode
  className?: string
}

export function CollapsibleSection({
  id,
  title,
  subtitle,
  summary,
  defaultOpen = true,
  children,
  className,
}: CollapsibleSectionProps) {
  const storageKey = `cc:section:${id}`
  const contentId = useId()
  const [open, setOpen] = useState(() => {
    try {
      const stored = localStorage.getItem(storageKey)
      return stored !== null ? stored === 'true' : defaultOpen
    } catch {
      return defaultOpen
    }
  })

  const toggle = () => {
    const next = !open
    setOpen(next)
    try { localStorage.setItem(storageKey, String(next)) } catch {}
  }

  return (
    <section className={cn('', className)}>
      <button
        className="flex w-full items-center gap-2 py-3 text-left group"
        onClick={toggle}
        aria-expanded={open}
        aria-controls={contentId}
      >
        <motion.span
          animate={{ rotate: open ? 90 : 0 }}
          transition={{ duration: 0.22, ease: 'easeOut' }}
          className="text-text-subtle group-hover:text-text-dim transition-colors"
        >
          <ChevronRight size={14} />
        </motion.span>
        <span className="kicker">{title}</span>
        {subtitle && <span className="text-xs text-text-subtle ml-1">{subtitle}</span>}
        {summary && <span className="ml-auto text-xs text-text-dim">{summary}</span>}
      </button>

      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            id={contentId}
            key="content"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.22, ease: 'easeOut' }}
            className="overflow-hidden"
          >
            <div className="pb-6">{children}</div>
          </motion.div>
        )}
      </AnimatePresence>
    </section>
  )
}
