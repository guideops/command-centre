import { useState } from 'react'
import { useSystemState } from '@/hooks/useQueries'
import { Button } from '@/components/ui/Button'
import { api } from '@/lib/api'
import { ShieldAlert, Play } from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import { motion, AnimatePresence } from 'framer-motion'

export function EmergencyStopBanner() {
  const { data: state } = useSystemState()
  const [confirm, setConfirm] = useState(false)
  const [stopping, setStopping] = useState(false)
  const [result, setResult] = useState<{ killed: number } | null>(null)
  const qc = useQueryClient()

  const isStopped = state?.emergency_stop === '1'

  const doStop = async () => {
    setStopping(true)
    try {
      const r = await api.emergencyStop()
      setResult({ killed: r.processes_killed })
      qc.invalidateQueries({ queryKey: ['state'] })
    } finally {
      setStopping(false)
      setConfirm(false)
    }
  }

  const doResume = async () => {
    await api.emergencyResume()
    setResult(null)
    qc.invalidateQueries({ queryKey: ['state'] })
  }

  if (isStopped) {
    return (
      <div className="rounded-xl border border-amber/30 bg-amber/5 px-4 py-3 flex items-center gap-3">
        <ShieldAlert size={16} className="text-amber flex-shrink-0" />
        <span className="text-sm text-amber font-medium flex-1">Emergency stop active — all dispatcher tasks halted</span>
        <Button size="sm" variant="secondary" onClick={doResume}>
          <Play size={11} /> Resume
        </Button>
      </div>
    )
  }

  return (
    <>
      <div className="flex justify-end">
        <Button variant="danger" size="sm" onClick={() => setConfirm(true)}>
          <ShieldAlert size={13} /> Emergency Stop
        </Button>
      </div>

      <AnimatePresence>
        {confirm && (
          <motion.div
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          >
            <motion.div
              className="bg-surface border border-red/30 rounded-xl p-6 w-full max-w-sm shadow-2xl"
              initial={{ scale: 0.95 }}
              animate={{ scale: 1 }}
              exit={{ scale: 0.95 }}
            >
              <div className="flex items-center gap-2 mb-3">
                <ShieldAlert size={18} className="text-red" />
                <h3 className="font-semibold text-red">Emergency Stop</h3>
              </div>
              <p className="text-sm text-text-dim mb-4">
                This will SIGTERM all active dispatcher-spawned <code className="font-mono text-xs">claude -p</code> processes
                and mark running tasks as failed. Interactive sessions in separate terminals are NOT affected.
              </p>
              <div className="flex gap-2 justify-end">
                <Button variant="ghost" size="sm" onClick={() => setConfirm(false)}>Cancel</Button>
                <Button variant="danger" size="sm" onClick={doStop} disabled={stopping}>
                  {stopping ? 'Stopping…' : 'Stop all agents'}
                </Button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {result && (
        <div className="rounded-xl border border-green/30 bg-green/5 px-4 py-2 text-sm text-green">
          Stopped {result.killed} process{result.killed !== 1 ? 'es' : ''}
        </div>
      )}
    </>
  )
}
