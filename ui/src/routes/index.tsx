import { motion } from 'framer-motion'
import { SystemHealthStrip } from '@/components/panels/SystemHealthStrip'
import { KpiRow } from '@/components/panels/KpiRow'
import { AttentionBar } from '@/components/panels/AttentionBar'
import { LiveSessionsCard } from '@/components/panels/LiveSessionsCard'
import { TokenUsageCard } from '@/components/panels/TokenUsageCard'
import { CollapsibleSection } from '@/components/ui/CollapsibleSection'
import {
  CacheEfficiencyCard,
  SessionOutcomesCard,
  ToolLatencyCard,
  HookActivityCard,
  ProjectBreakdownCard,
  AgentFanoutCard,
  EditAcceptanceCard,
  ProductivityCard,
  PressurePanel,
} from '@/components/panels/ObservabilityPanels'
import { DecisionsCard, InboxCard } from '@/components/panels/HITLPanels'
import { TaskBoard } from '@/components/panels/TaskBoard'
import { SchedulesCard } from '@/components/panels/SchedulesCard'
import { EmergencyStopBanner } from '@/components/panels/EmergencyStopBanner'

const fadeUp = { initial: { opacity: 0, y: 6 }, animate: { opacity: 1, y: 0 }, transition: { duration: 0.3 } }

export function CommandPage() {
  return (
    <motion.div {...fadeUp} className="space-y-4">
      {/* Always-visible strip */}
      <SystemHealthStrip />
      <KpiRow />
      <AttentionBar />

      {/* Live sessions */}
      <CollapsibleSection id="live-sessions" title="Live Sessions" defaultOpen>
        <LiveSessionsCard />
      </CollapsibleSection>

      {/* Token usage */}
      <CollapsibleSection id="token-usage" title="Token Usage" defaultOpen>
        <TokenUsageCard />
      </CollapsibleSection>

      {/* Observability */}
      <CollapsibleSection id="observability" title="Observability" defaultOpen>
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4 auto-rows-fr [&>*]:h-full">
            <CacheEfficiencyCard />
            <SessionOutcomesCard />
          </div>
          <div className="grid grid-cols-2 gap-4 auto-rows-fr [&>*]:h-full">
            <ToolLatencyCard />
            <HookActivityCard />
          </div>
          <div className="grid grid-cols-2 gap-4 auto-rows-fr [&>*]:h-full">
            <ProjectBreakdownCard />
            <AgentFanoutCard />
          </div>
          <div className="grid grid-cols-2 gap-4 auto-rows-fr [&>*]:h-full">
            <EditAcceptanceCard />
            <ProductivityCard />
          </div>
          <PressurePanel />
        </div>
      </CollapsibleSection>

      {/* HITL */}
      <CollapsibleSection id="hitl" title="Human-in-the-Loop" defaultOpen>
        <div className="grid grid-cols-2 gap-4 auto-rows-fr [&>*]:h-full">
          <DecisionsCard />
          <InboxCard />
        </div>
      </CollapsibleSection>

      {/* Mission Control */}
      <CollapsibleSection id="mission-control" title="Mission Control" defaultOpen>
        <div className="space-y-4">
          <TaskBoard />
          <SchedulesCard />
        </div>
      </CollapsibleSection>

      {/* Emergency stop */}
      <div className="pb-4">
        <EmergencyStopBanner />
      </div>
    </motion.div>
  )
}
