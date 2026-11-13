<template>
  <section class="card branching-card">
    <header class="card-head">
      <div>
        <h3>{{ $t('analytics.branchingTitle') }}</h3>
        <p class="sub">{{ $t('analytics.branchingSubtitle') }}</p>
      </div>
    </header>

    <div class="gauges">
      <div class="gauge">
        <svg viewBox="0 0 120 70" class="arc">
          <path d="M10 60 A50 50 0 0 1 110 60" class="track" />
          <path d="M10 60 A50 50 0 0 1 110 60" class="value"
            :stroke-dasharray="arcLen"
            :stroke-dashoffset="arcOffset(branching)" />
          <text x="60" y="52" text-anchor="middle" class="gauge-num">{{ display(branching) }}</text>
        </svg>
        <div class="gauge-label">{{ $t('analytics.branchingFactor') }}</div>
        <p class="gauge-hint">{{ branchingHint }}</p>
      </div>

      <div class="gauge">
        <svg viewBox="0 0 120 70" class="arc">
          <path d="M10 60 A50 50 0 0 1 110 60" class="track" />
          <path d="M10 60 A50 50 0 0 1 110 60" class="value orphan"
            :stroke-dasharray="arcLen"
            :stroke-dashoffset="arcOffset(orphanShare)" />
          <text x="60" y="52" text-anchor="middle" class="gauge-num">{{ pct(orphanShare) }}</text>
        </svg>
        <div class="gauge-label">{{ $t('analytics.orphanShare') }}</div>
        <p class="gauge-hint">{{ $t('analytics.orphanShareHint', { count: orphanCount, roots: roots }) }}</p>
      </div>

      <div class="stat-col">
        <div class="stat"><span class="k">{{ $t('analytics.maxDepth') }}</span><span class="v">{{ summary?.max_depth ?? '–' }}</span></div>
        <div class="stat"><span class="k">{{ $t('analytics.maxSize') }}</span><span class="v">{{ summary?.max_size ?? '–' }}</span></div>
        <div class="stat"><span class="k">{{ $t('analytics.meanVirality') }}</span><span class="v">{{ display(summary?.mean_virality) }}</span></div>
        <div class="stat"><span class="k">{{ $t('analytics.silentAgents') }}</span><span class="v">{{ silentCount }}</span></div>
      </div>
    </div>

    <div v-if="silentAgents.length" class="silent">
      <div class="silent-title">{{ $t('analytics.silentAgentsList') }}</div>
      <div class="chips">
        <span v-for="name in silentAgents.slice(0, 24)" :key="name" class="chip">{{ name }}</span>
        <span v-if="silentAgents.length > 24" class="chip more">+{{ silentAgents.length - 24 }}</span>
      </div>
    </div>

    <p class="consensus" v-if="consensus">
      <strong>{{ $t('analytics.consensusLabel') }}:</strong> {{ consensus.plain }}
    </p>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { pct } from './palette'

const props = defineProps({
  summary: { type: Object, default: null },
  orphans: { type: Object, default: null },
  consensus: { type: Object, default: null }
})
const { t } = useI18n()

const branching = computed(() => props.summary?.branching_factor)
const orphanShare = computed(() => props.orphans?.cascade_orphan_share ?? props.summary?.orphan_share ?? 0)
const orphanCount = computed(() => props.orphans?.cascade_orphans ?? 0)
const roots = computed(() => props.summary?.roots ?? 0)
const silentAgents = computed(() => props.orphans?.silent_agents || [])
const silentCount = computed(() => props.orphans?.silent_agent_count ?? silentAgents.value.length)

const arcLen = Math.PI * 50
// Map 0..1.5 branching (or 0..1 share) onto the semicircle
const arcOffset = (val) => {
  const v = val == null ? 0 : Number(val)
  const capped = Math.max(0, Math.min(1, v > 1 ? v / 1.5 : v))
  return arcLen * (1 - capped)
}

const display = (v) => (v === null || v === undefined ? '–' : Number(v).toFixed(2))

const branchingHint = computed(() => {
  const b = branching.value
  if (b == null) return t('analytics.branchingUnknown')
  if (b < 0.3) return t('analytics.branchingLow')
  if (b < 1) return t('analytics.branchingMid')
  return t('analytics.branchingHigh')
})
</script>

<style scoped>
.gauges { display: grid; grid-template-columns: 1fr 1fr minmax(160px, 0.9fr); gap: 16px; align-items: start; }
.gauge { text-align: center; }
.arc { width: 140px; height: 82px; }
.track { fill: none; stroke: var(--hm-surface-3); stroke-width: 10; stroke-linecap: round; }
.value { fill: none; stroke: #2a78d6; stroke-width: 10; stroke-linecap: round; }
.value.orphan { stroke: #898781; }
.gauge-num { font-family: var(--hm-font-display); font-size: 16px; font-weight: 500; fill: var(--hm-ink); }
.gauge-label { font-size: 12px; font-weight: 600; color: var(--hm-ink); margin-top: 2px; }
.gauge-hint { margin: 4px 0 0; font-size: 12px; color: var(--hm-ink-3); line-height: 1.4; }
.stat-col { display: flex; flex-direction: column; gap: 8px; padding-top: 8px; }
.stat { display: flex; justify-content: space-between; gap: 12px; font-size: 12px; border-bottom: 1px solid var(--hm-line); padding-bottom: 6px; }
.stat .k { color: var(--hm-ink-4); }
.stat .v { font-variant-numeric: tabular-nums; font-weight: 600; color: var(--hm-ink); }
.silent { margin-top: 14px; }
.silent-title { font-size: 12px; font-weight: 600; margin-bottom: 8px; color: var(--hm-ink); }
.chips { display: flex; flex-wrap: wrap; gap: 6px; }
.chip {
  font-size: 11px; padding: 3px 8px; border-radius: 999px;
  background: var(--hm-surface-3); color: var(--hm-ink-2);
}
.chip.more { background: transparent; border: 1px dashed var(--hm-line-strong); }
.consensus { margin: 14px 0 0; font-size: 13px; color: var(--hm-ink-2); line-height: 1.45; }
@media (max-width: 900px) {
  .gauges { grid-template-columns: 1fr; }
}
</style>
