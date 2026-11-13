<template>
  <div class="hm-analytics">
    <header class="app-header">
      <div class="header-left">
        <div class="brand" @click="router.push('/')">MIROFISH</div>
        <span class="divider"></span>
        <span class="page-title">{{ $t('analytics.title') }}</span>
        <span class="sim-id">{{ simulationId }}</span>
      </div>
      <div class="header-right">
        <span class="status" :class="statusClass"><span class="dot"></span>{{ statusText }}</span>
        <span v-if="isLive" class="auto">{{ $t('analytics.autoRefresh') }}</span>
        <button class="ghost-btn" :disabled="loading" @click="load">{{ $t('analytics.refresh') }}</button>
        <button class="ghost-btn" @click="router.push({ name: 'SimulationRun', params: { simulationId } })">
          ← {{ $t('analytics.backToSimulation') }}
        </button>
        <LanguageSwitcher />
      </div>
    </header>

    <main class="page">
      <p v-if="error" class="banner error">{{ $t('analytics.loadFailed', { error }) }}</p>
      <p v-if="!data && loading" class="banner">{{ $t('analytics.loading') }}</p>

      <template v-if="data">
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

        <section class="grid-main">
          <InfluenceNetwork
            :agents="data.agents"
            :edges="data.edges"
            :max-round="maxRound"
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
import LanguageSwitcher from '../components/LanguageSwitcher.vue'
import InfluenceNetwork from '../components/analytics/InfluenceNetwork.vue'
import InfluencerBars from '../components/analytics/InfluencerBars.vue'
import AgentDetail from '../components/analytics/AgentDetail.vue'
import ActivityChart from '../components/analytics/ActivityChart.vue'
import TopPosts from '../components/analytics/TopPosts.vue'
import ActionMix from '../components/analytics/ActionMix.vue'
import { getSimulationAnalytics } from '../api/simulation'
import { fmt, pct } from '../components/analytics/palette'

const props = defineProps({ simulationId: { type: String, required: true } })
const router = useRouter()
const route = useRoute()
const { t: tr } = useI18n()

const POLL_MS = 5000
const data = ref(null)
const loading = ref(false)
const error = ref('')
const selected = ref(typeof route.query.agent === 'string' ? route.query.agent : null)
watch(selected, (name) => {
  router.replace({ query: { ...route.query, agent: name || undefined } })
})
let timer = null

const t = computed(() => data.value?.totals || {})
const isLive = computed(() => ['running', 'starting', 'stopping'].includes(data.value?.run?.status))
const maxRound = computed(() => Math.max(0, (data.value?.rounds?.length || 1) - 1))
const roundsDone = computed(() => {
  const rounds = data.value?.rounds || []
  const last = [...rounds].reverse().find(r => r.total > 0)
  return last ? last.round + 1 : 0
})
const supportShare = computed(() => {
  const s = t.value.support || 0
  const o = t.value.oppose || 0
  return s + o ? pct(s / (s + o)) : '–'
})

const statusText = computed(() => {
  const s = data.value?.run?.status
  if (isLive.value) return tr('analytics.live')
  if (s === 'completed' || s === 'stopped') return tr('analytics.finished')
  if (!s || s === 'idle') return t.value.actions ? tr('analytics.finished') : tr('analytics.notStarted')
  return s
})
const statusClass = computed(() => (isLive.value ? 'live' : t.value.actions ? 'done' : 'idle'))

const load = async () => {
  loading.value = true
  try {
    const res = await getSimulationAnalytics(props.simulationId)
    data.value = res.data
    error.value = ''
  } catch (e) {
    error.value = e.message || String(e)
  } finally {
    loading.value = false
  }
  schedule()
}

const schedule = () => {
  clearTimeout(timer)
  if (isLive.value) timer = setTimeout(load, POLL_MS)
}

onMounted(load)
onUnmounted(() => clearTimeout(timer))
</script>

<style scoped>
.hm-analytics { min-height: 100vh; background: #fafaf9; color: #0b0b0b; font-family: Inter, system-ui, -apple-system, 'Segoe UI', sans-serif; }
.app-header {
  height: 60px; display: flex; align-items: center; justify-content: space-between; padding: 0 24px;
  background: #fff; border-bottom: 1px solid #eaeaea; position: sticky; top: 0; z-index: 50;
}
.header-left, .header-right { display: flex; align-items: center; gap: 14px; }
.brand { font-family: 'JetBrains Mono', monospace; font-weight: 800; font-size: 18px; letter-spacing: 1px; cursor: pointer; }
.divider { width: 1px; height: 18px; background: #e0e0e0; }
.page-title { font-weight: 600; font-size: 14px; }
.sim-id { font-family: 'JetBrains Mono', monospace; font-size: 11px; color: #898781; }
.status { display: inline-flex; align-items: center; gap: 6px; font-size: 12px; color: #52514e; }
.status .dot { width: 8px; height: 8px; border-radius: 50%; background: #c3c2b7; }
.status.live .dot { background: #0ca30c; animation: pulse 1.4s ease-in-out infinite; }
.status.done .dot { background: #0b0b0b; }
.auto { font-size: 11px; color: #898781; }
@keyframes pulse { 50% { opacity: 0.35; } }

.page { max-width: 1440px; margin: 0 auto; padding: 24px; display: flex; flex-direction: column; gap: 20px; }
.banner { margin: 0; padding: 12px 16px; background: #fff; border: 1px solid #eaeaea; border-radius: 8px; font-size: 13px; color: #52514e; }
.banner.error { border-color: #d03b3b; color: #d03b3b; }

.kpis { display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 12px; }
.kpi { background: #fff; border: 1px solid #eaeaea; border-radius: 8px; padding: 14px 16px; display: flex; flex-direction: column; gap: 4px; }
.kpi-label { font-family: 'JetBrains Mono', monospace; font-size: 10px; letter-spacing: 0.08em; text-transform: uppercase; color: #898781; }
.kpi-value { font-size: 26px; font-weight: 600; line-height: 1.1; }
.kpi-value small { font-size: 14px; font-weight: 500; color: #898781; }
.kpi-foot { font-size: 11px; color: #52514e; }

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
.hm-analytics .card { background: #fff; border: 1px solid #eaeaea; border-radius: 8px; padding: 18px 20px; }
.hm-analytics .card-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; margin-bottom: 12px; }
.hm-analytics .card-head h3 { margin: 0; font-size: 15px; font-weight: 600; letter-spacing: -0.01em; }
.hm-analytics .card-head .sub { margin: 3px 0 0; font-size: 12px; color: #52514e; }
.hm-analytics .legend { list-style: none; display: flex; flex-wrap: wrap; gap: 14px; margin: 0 0 10px; padding: 0; font-size: 12px; color: #0b0b0b; }
.hm-analytics .legend li { display: inline-flex; align-items: center; gap: 6px; }
.hm-analytics .sw { display: inline-block; width: 10px; height: 10px; border-radius: 2px; flex-shrink: 0; vertical-align: middle; }
.hm-analytics .ghost-btn {
  background: #fff; border: 1px solid #ddd; border-radius: 4px; padding: 5px 10px; font-size: 12px;
  color: #0b0b0b; cursor: pointer; white-space: nowrap; font-family: inherit;
}
.hm-analytics .ghost-btn:hover:not(:disabled) { border-color: #999; }
.hm-analytics .ghost-btn:disabled { opacity: 0.4; cursor: default; }
.hm-analytics .seg-toggle { display: inline-flex; border: 1px solid #ddd; border-radius: 4px; overflow: hidden; }
.hm-analytics .card-head .seg-toggle button { background: #fff; border: none; padding: 5px 10px; font-size: 12px; cursor: pointer; color: #52514e; font-family: inherit; }
.hm-analytics .card-head .seg-toggle button.on { background: #0b0b0b; color: #fff; }
.hm-analytics .tip {
  position: absolute; z-index: 20; pointer-events: none; min-width: 150px; background: #fff;
  border: 1px solid rgba(11, 11, 11, 0.1); border-radius: 6px; box-shadow: 0 6px 20px rgba(0, 0, 0, 0.08);
  padding: 8px 10px; font-size: 12px; color: #52514e;
}
.hm-analytics .tip-title { font-weight: 600; color: #0b0b0b; margin-bottom: 4px; }
.hm-analytics .tip-row { display: flex; align-items: center; gap: 6px; line-height: 1.7; }
.hm-analytics .tip-row strong { color: #0b0b0b; font-variant-numeric: tabular-nums; min-width: 28px; text-align: right; }
.hm-analytics .table-wrap { max-height: 320px; overflow: auto; border: 1px solid #f0f0ee; border-radius: 6px; }
.hm-analytics .table-wrap table { width: 100%; border-collapse: collapse; font-size: 12px; }
.hm-analytics .table-wrap th {
  position: sticky; top: 0; background: #fafaf9; text-align: right; font-weight: 500; color: #52514e;
  padding: 6px 10px; border-bottom: 1px solid #eaeaea;
}
.hm-analytics .table-wrap td { text-align: right; padding: 5px 10px; border-bottom: 1px solid #f4f4f2; font-variant-numeric: tabular-nums; }
.hm-analytics .table-wrap th:first-child, .hm-analytics .table-wrap td:first-child { text-align: left; }
</style>
