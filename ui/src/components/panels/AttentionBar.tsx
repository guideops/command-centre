import { useAttention } from '@/hooks/useQueries'
import { AlertTriangle } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'

export function AttentionBar() {
  const { data } = useAttention()

  if (!data || data.all_clear) return null

  return (
    <AnimatePresence>
      <motion.div
        initial={{ height: 0, opacity: 0 }}
        animate={{ height: 'auto', opacity: 1 }}
        exit={{ height: 0, opacity: 0 }}
        className="overflow-hidden"
      >
        <div className="rounded-xl border border-red/30 bg-red/5 px-4 py-3 flex items-start gap-3">
          <AlertTriangle size={15} className="text-red flex-shrink-0 mt-0.5" />
          <div className="flex-1">
            <div className="text-xs font-semibold text-red mb-1">Attention required</div>
            <div className="flex flex-wrap gap-x-4 gap-y-1">
              {data.issues.map((issue, i) => (
                <span key={i} className="text-xs text-red/80">{issue.message}</span>
              ))}
            </div>
          </div>
        </div>
      </motion.div>
    </AnimatePresence>
  )
}
