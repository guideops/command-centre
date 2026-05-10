import { useState, useRef, ReactNode } from 'react'
import { cn } from '@/lib/utils'

interface TooltipProps {
  content: ReactNode
  children: ReactNode
  className?: string
}

export function Tooltip({ content, children, className }: TooltipProps) {
  const [show, setShow] = useState(false)
  const timer = useRef<ReturnType<typeof setTimeout>>()

  return (
    <div
      className={cn('relative inline-flex', className)}
      onMouseEnter={() => { timer.current = setTimeout(() => setShow(true), 400) }}
      onMouseLeave={() => { clearTimeout(timer.current); setShow(false) }}
    >
      {children}
      {show && (
        <div
          className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 z-50 whitespace-nowrap"
          role="tooltip"
        >
          <div className="rounded-md bg-surface-2 border border-border px-2 py-1 text-xs text-text shadow-lg">
            {content}
          </div>
          <div className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-border" />
        </div>
      )}
    </div>
  )
}
