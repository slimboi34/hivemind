<template>
  <div class="hm-analytics">
    <AppHeader>
      <template #context>
        <span class="page-title">{{ $t('analytics.title') }}</span>
        <span class="sim-id">{{ simulationId }}</span>
      </template>
      <span v-if="isLive" class="auto">{{ $t('analytics.autoRefresh') }}</span>
      <span
        class="hm-pill"
        :class="{ 'hm-pill--active': statusClass === 'live', 'hm-pill--success': statusClass === 'done' }"
      >
        <span class="hm-pill__dot"></span>{{ statusText }}
      </span>
      <button class="hm-btn hm-btn--secondary hm-btn--sm" :disabled="loading" @click="load">{{ $t('analytics.refresh') }}</button>
      <button class="hm-btn hm-btn--secondary hm-btn--sm" :disabled="downloadingPdf" @click="downloadPdf">
        {{ downloadingPdf ? $t('analytics.briefPreparingPdf') : $t('analytics.downloadPdf') }}
      </button>
      <button class="hm-btn hm-btn--secondary hm-btn--sm" @click="router.push({ name: 'SimulationRun', params: { simulationId } })">
        ← {{ $t('analytics.backToSimulation') }}
      </button>
    </AppHeader>

    <main class="page">
      <p v-if="error" class="banner error">{{ $t('analytics.loadFailed', { error }) }}</p>
      <p v-if="!data && loading" class="banner">{{ $t('analytics.loading') }}</p>

      <p v-if="pdfError" class="banner error">{{ $t('analytics.briefPdfFailed', { error: pdfError }) }}</p>

      <template v-if="data">
        <Briefing
          :briefing="briefing"
          :writing="writingBriefing"
          :write-error="briefingError"
          :downloading="downloadingPdf"
          v-model:selected="selected"
          @write="writeBriefing"
          @download="downloadPdf"
        />

        <WhatHappened
          :recap="recap"
          :writing="writingRecap"
          :write-error="recapError"
          v-model:selected="selected"
          @write="writeRecap"
        />

        <CastTree :simulation-id="simulationId" :live="isLive" v-model:selected="selected" @loaded="onCast" />

        <HealthBadge v-if="dynamics?.health" :health="dynamics.health" />

        <section class="kpis">
          <div class="kpi">
            <span class="kpi-label">{{ $t('analytics.kpiActions') }}</span>
            <span class="kpi-value">{{ fmt(t.actions) }}</span>
            <span class="kpi-foot">{{ $t('analytics.platforms.twitter') }} {{ fmt(t.twitter) }} · {{ $t('analytics.platforms.reddit') }} {{ fmt(t.reddit) }}</span>
          </div>
          <div class="kpi">
            <span class="kpi-label">{{ $t('analytics.kpiAgents') }}</span>
            <span class="kpi-value">{{ fmt(t.agents_active) }}</span>
          </div>
          <div class="kpi">
            <span class="kpi-label">{{ $t('analytics.kpiPosts') }}</span>
            <span class="kpi-value">{{ fmt(t.post) }}</span>
          </div>
          <div class="kpi">
            <span class="kpi-label">{{ $t('analytics.kpiInteractions') }}</span>
            <span class="kpi-value">{{ fmt(t.interactions) }}</span>
          </div>
          <div class="kpi" :title="$t('analytics.kpiApprovalHint')">
            <span class="kpi-label">{{ $t('analytics.kpiApproval') }}</span>
            <span class="kpi-value">{{ supportShare }}</span>
            <span class="kpi-foot">{{ fmt(t.support) }} {{ $t('analytics.categories.support').toLowerCase() }} · {{ fmt(t.oppose) }} {{ $t('analytics.categories.oppose').toLowerCase() }}</span>
          </div>
          <div class="kpi">
            <span class="kpi-label">{{ $t('analytics.kpiRounds') }}</span>
            <span class="kpi-value">{{ roundsDone }}<small v-if="data.run.total_rounds"> / {{ data.run.total_rounds }}</small></span>
          </div>
        </section>

        <p v-if="!t.actions" class="banner">{{ $t('analytics.empty') }}</p>

        <BranchingPanel
          v-if="dynamics"
          :summary="dynamics.cascades?.summary"
          :orphans="dynamics.orphans"
          :consensus="dynamics.consensus"
        />

        <CascadeForest v-if="dynamics?.cascades?.top?.length" :cascades="dynamics.cascades.top" />

        <section class="grid-main">
          <InfluenceNetwork
            :agents="data.agents"
            :edges="data.edges"
            :max-round="maxRound"
            :agent-groups="agentGroups"
            :group-labels="groupLabels"
            v-model:selected="selected"
          />
          <div class="side">
            <AgentDetail :agents="data.agents" :edges="data.edges" v-model:selected="selected" />
            <InfluencerBars :agents="data.agents" v-model:selected="selected" />
          </div>
        </section>

        <ActivityChart :rounds="data.rounds" />

        <section class="grid-two">
          <TopPosts :posts="data.top_posts" v-model:selected="selected" />
          <ActionMix :action-types="data.action_types" />
        </section>
      </template>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import AppHeader from '../components/AppHeader.vue'
import InfluenceNetwork from '../components/analytics/InfluenceNetwork.vue'
import InfluencerBars from '../components/analytics/InfluencerBars.vue'
import AgentDetail from '../components/analytics/AgentDetail.vue'
import ActivityChart from '../components/analytics/ActivityChart.vue'
import TopPosts from '../components/analytics/TopPosts.vue'
import ActionMix from '../components/analytics/ActionMix.vue'
import HealthBadge from '../components/analytics/HealthBadge.vue'
import CascadeForest from '../components/analytics/CascadeForest.vue'
import BranchingPanel from '../components/analytics/BranchingPanel.vue'
import WhatHappened from '../components/analytics/WhatHappened.vue'
import Briefing from '../components/analytics/Briefing.vue'
import CastTree from '../components/analytics/CastTree.vue'
import {
  getSimulationAnalytics,
  getSimulationDynamics,
  getSimulationRecap,
  writeSimulationRecap,
  getSimulationBriefing,
  writeSimulationBriefing,
  downloadBriefingPdf
} from '../api/simulation'
import { fmt, pct } from '../components/analytics/palette'

const props = defineProps({ simulationId: { type: String, required: true } })
const router = useRouter()
const route = useRoute()
const { t: tr } = useI18n()

const POLL_MS = 5000
const data = ref(null)
const dynamics = ref(null)
const recap = ref(null)
const writingRecap = ref(false)
const recapError = ref('')
let autoWriteTried = false
const briefing = ref(null)
const writingBriefing = ref(false)
const briefingError = ref('')
let autoBriefTried = false
const downloadingPdf = ref(false)
// name -> group key, from the cast tree; lets the network colour nodes by group.
const agentGroups = ref({})
const groupLabels = ref({})
const onCast = (cast) => {
  const map = {}
  const labels = {}
  for (const g of cast?.groups || []) {
    labels[g.key] = g.label
    for (const t of g.types) for (const a of t.agents) map[a.name] = g.key
  }
  agentGroups.value = map
  groupLabels.value = labels
}
const pdfError = ref('')
const loading = ref(false)
const error = ref('')
const selected = ref(typeof route.query.agent === 'string' ? route.query.agent : null)
watch(selected, (name) => {
  router.replace({ query: { ...route.query, agent: name || undefined } })
})
let timer = null

const t = computed(() => data.value?.totals || {})
// A run stays "running" after its last round while agents are kept alive for
// interviews. Once every round has been played there is nothing left to watch.
const isLive = computed(() =>
  ['running', 'starting', 'stopping'].includes(data.value?.run?.status) && !briefing.value?.facts?.run?.finished
)
const maxRound = computed(() => Math.max(0, (data.value?.rounds?.length || 1) - 1))
const roundsDone = computed(() => {
  const rounds = data.value?.rounds || []
  const last = [...rounds].reverse().find(r => r.total > 0)
  return last ? last.round : 0 // round 0 is the seeding round (initial posts)
})
const supportShare = computed(() => {
  const s = t.value.support || 0
  const o = t.value.oppose || 0
  return s + o ? pct(s / (s + o)) : '–'
})

const statusText = computed(() => {
  const s = data.value?.run?.status
  if (isLive.value) return tr('analytics.live')
  if (s === 'completed' || s === 'stopped' || briefing.value?.facts?.run?.finished) return tr('analytics.finished')
  if (!s || s === 'idle') return t.value.actions ? tr('analytics.finished') : tr('analytics.notStarted')
  return s
})
const statusClass = computed(() => (isLive.value ? 'live' : t.value.actions ? 'done' : 'idle'))

const load = async () => {
  loading.value = true
  try {
    const [analyticsRes, dynamicsRes, recapRes, briefingRes] = await Promise.all([
      getSimulationAnalytics(props.simulationId),
      getSimulationDynamics(props.simulationId).catch(() => null),
      writingRecap.value ? Promise.resolve(null) : getSimulationRecap(props.simulationId).catch(() => null),
      writingBriefing.value ? Promise.resolve(null) : getSimulationBriefing(props.simulationId).catch(() => null)
    ])
    data.value = analyticsRes.data
    dynamics.value = dynamicsRes?.data || null
    if (recapRes?.data) recap.value = recapRes.data
    if (briefingRes?.data) briefing.value = briefingRes.data
    error.value = ''
    maybeAutoWrite()
    maybeAutoBrief()
  } catch (e) {
    error.value = e.message || String(e)
  } finally {
    loading.value = false
  }
  schedule()
}

// Once a run has finished, have the AI write its story the first time anyone opens it.
// The backend caches it, so later visits get it instantly.
const maybeAutoWrite = () => {
  const r = recap.value
  if (autoWriteTried || !r || r.story_source === 'llm' || !r.can_write || !r.facts?.run?.finished) return
  autoWriteTried = true
  writeRecap(false)
}

// Same for the briefing: written once per finished run, then served from the cache.
const maybeAutoBrief = () => {
  const b = briefing.value
  if (autoBriefTried || !b || b.reading_source === 'llm' || !b.can_write || !b.facts?.run?.finished) return
  autoBriefTried = true
  writeBriefing(false)
}

const writeBriefing = async (force = false) => {
  if (writingBriefing.value) return
  writingBriefing.value = true
  briefingError.value = ''
  try {
    const res = await writeSimulationBriefing(props.simulationId, force)
    briefing.value = res.data
  } catch (e) {
    briefingError.value = e.message || String(e)
  } finally {
    writingBriefing.value = false
  }
}

// The PDF waits for the AI reading and story if they are not written yet, so
// fetch it in the background and show progress instead of a dead-looking link.
const downloadPdf = async () => {
  if (downloadingPdf.value) return
  downloadingPdf.value = true
  pdfError.value = ''
  try {
    await downloadBriefingPdf(props.simulationId)
    load()
  } catch (e) {
    pdfError.value = e.message || String(e)
  } finally {
    downloadingPdf.value = false
  }
}

const writeRecap = async (force = false) => {
  if (writingRecap.value) return
  writingRecap.value = true
  recapError.value = ''
  try {
    const res = await writeSimulationRecap(props.simulationId, force)
    recap.value = res.data
  } catch (e) {
    recapError.value = e.message || String(e)
  } finally {
    writingRecap.value = false
  }
}

const schedule = () => {
  clearTimeout(timer)
  if (isLive.value) timer = setTimeout(load, POLL_MS)
}

onMounted(load)
onUnmounted(() => clearTimeout(timer))
</script>

<style scoped>
.hm-analytics { min-height: 100vh; background: var(--hm-paper); color: var(--hm-ink); font-family: var(--hm-font-sans); }
.page-title { font-family: var(--hm-font-mono); font-size: var(--hm-text-2xs); letter-spacing: 0.1em; text-transform: uppercase; color: var(--hm-paper); }
.sim-id { font-family: var(--hm-font-mono); font-size: var(--hm-text-2xs); color: var(--hm-nav-text); }
.auto { font-family: var(--hm-font-mono); font-size: var(--hm-text-2xs); color: var(--hm-nav-text); }

.page { max-width: 1440px; margin: 0 auto; padding: var(--hm-space-6); display: flex; flex-direction: column; gap: var(--hm-space-5); }
.banner { margin: 0; padding: var(--hm-space-3) var(--hm-space-4); background: var(--hm-surface); border: 1px solid var(--hm-line); border-radius: var(--hm-radius-md); font-size: var(--hm-text-sm); color: var(--hm-ink-3); }
.banner.error { background: var(--hm-danger-soft); border-color: transparent; color: var(--hm-danger); }

.kpis { display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: var(--hm-space-3); }
.kpi { background: var(--hm-surface); border: 1px solid var(--hm-line); border-radius: var(--hm-radius-lg); padding: var(--hm-space-4) var(--hm-space-5); display: flex; flex-direction: column; gap: 6px; }
.kpi-label { font-size: var(--hm-text-2xs); font-weight: 500; font-family: var(--hm-font-mono); letter-spacing: var(--hm-tracking-label); text-transform: uppercase; color: var(--hm-ink-4); }
.kpi-value { font-family: var(--hm-font-display); font-size: var(--hm-text-2xl); font-weight: 500; letter-spacing: var(--hm-tracking-display); line-height: 1.05; font-variant-numeric: tabular-nums; }
.kpi-value small { font-size: var(--hm-text-base); font-weight: 500; letter-spacing: 0; color: var(--hm-ink-4); }
.kpi-foot { font-size: var(--hm-text-2xs); color: var(--hm-ink-3); }

.grid-main { display: grid; grid-template-columns: minmax(0, 2fr) minmax(320px, 1fr); gap: 20px; align-items: start; }
.side { display: flex; flex-direction: column; gap: 20px; }
.grid-two { display: grid; grid-template-columns: minmax(0, 3fr) minmax(0, 2fr); gap: 20px; align-items: start; }

@media (max-width: 1100px) {
  .kpis { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .grid-main, .grid-two { grid-template-columns: 1fr; }
}
</style>

<!-- Shared, unscoped card styles for the analytics components; namespaced under .hm-analytics. -->
<style>
.hm-analytics .card { background: var(--hm-surface); border: 1px solid var(--hm-line); border-radius: var(--hm-radius-lg); padding: var(--hm-space-5) var(--hm-space-6); }
.hm-analytics .card-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; margin-bottom: 12px; }
.hm-analytics .card-head h3 { margin: 0; font-family: var(--hm-font-display); font-size: var(--hm-text-md); font-weight: 500; letter-spacing: -0.01em; }
.hm-analytics .card-head .sub { margin: 4px 0 0; font-size: var(--hm-text-xs); color: var(--hm-ink-4); }
.hm-analytics .legend { list-style: none; display: flex; flex-wrap: wrap; gap: 14px; margin: 0 0 10px; padding: 0; font-size: 12px; color: var(--hm-ink); }
.hm-analytics .legend li { display: inline-flex; align-items: center; gap: 6px; }
.hm-analytics .sw { display: inline-block; width: 10px; height: 10px; border-radius: 2px; flex-shrink: 0; vertical-align: middle; }
.hm-analytics .ghost-btn {
  height: 28px; padding: 0 var(--hm-space-3); background: var(--hm-surface); border: 1px solid var(--hm-line-strong);
  border-radius: var(--hm-radius-sm); font-size: var(--hm-text-xs); font-weight: 600; color: var(--hm-ink);
  cursor: pointer; white-space: nowrap; font-family: inherit;
}
.hm-analytics .ghost-btn:hover:not(:disabled) { border-color: var(--hm-ink-5); background: var(--hm-surface-2); }
.hm-analytics .ghost-btn:disabled { opacity: 0.4; cursor: default; }
.hm-analytics .seg-toggle { display: inline-flex; gap: 2px; padding: 3px; background: var(--hm-surface-3); border-radius: var(--hm-radius-md); }
.hm-analytics .card-head .seg-toggle button { height: 26px; padding: 0 var(--hm-space-3); background: transparent; border: none; border-radius: var(--hm-radius-sm); font-size: var(--hm-text-xs); font-weight: 600; cursor: pointer; color: var(--hm-ink-3); font-family: inherit; }
.hm-analytics .card-head .seg-toggle button.on { background: var(--hm-surface); color: var(--hm-ink); box-shadow: var(--hm-shadow-xs); }
.hm-analytics .tip {
  position: absolute; z-index: 20; pointer-events: none; min-width: 150px; background: var(--hm-surface);
  border: 1px solid var(--hm-line); border-radius: var(--hm-radius-md); box-shadow: var(--hm-shadow-md);
  padding: 8px 10px; font-size: 12px; color: var(--hm-ink-3);
}
.hm-analytics .tip-title { font-weight: 600; color: var(--hm-ink); margin-bottom: 4px; }
.hm-analytics .tip-row { display: flex; align-items: center; gap: 6px; line-height: 1.7; }
.hm-analytics .tip-row strong { color: var(--hm-ink); font-variant-numeric: tabular-nums; min-width: 28px; text-align: right; }
.hm-analytics .table-wrap { max-height: 320px; overflow: auto; border: 1px solid var(--hm-line); border-radius: var(--hm-radius-md); }
.hm-analytics .table-wrap table { width: 100%; border-collapse: collapse; font-size: 12px; }
.hm-analytics .table-wrap th {
  position: sticky; top: 0; background: var(--hm-surface-2); text-align: right; font-weight: 500; color: var(--hm-ink-3);
  padding: 6px 10px; border-bottom: 1px solid var(--hm-line);
}
.hm-analytics .table-wrap td { text-align: right; padding: 5px 10px; border-bottom: 1px solid var(--hm-surface-3); font-variant-numeric: tabular-nums; }
.hm-analytics .table-wrap th:first-child, .hm-analytics .table-wrap td:first-child { text-align: left; }
</style>
