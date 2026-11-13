<template>
  <section class="card agent-detail">
    <template v-if="agent">
      <header class="card-head">
        <div>
          <p class="eyebrow">{{ $t('analytics.agentDetail') }}</p>
          <h3 class="agent-name">{{ agent.name }}</h3>
          <p v-if="agent.first_round !== null" class="sub">{{ $t('analytics.firstActive', { round: agent.first_round }) }}</p>
        </div>
        <button class="ghost-btn" @click="emit('update:selected', null)">{{ $t('analytics.clearSelection') }}</button>
      </header>

      <div class="stats">
        <div><strong>{{ fmt(agent.engagement_received) }}</strong><span>{{ $t('analytics.engagement') }}</span></div>
        <div :title="$t('analytics.reachHint')"><strong>{{ fmt(agent.reach) }}</strong><span>{{ $t('analytics.reach') }}</span></div>
        <div :title="$t('analytics.kpiApprovalHint')"><strong>{{ pct(agent.approval) }}</strong><span>{{ $t('analytics.approval') }}</span></div>
        <div><strong>{{ fmt(agent.actions) }}</strong><span>{{ $t('analytics.actions') }}</span></div>
      </div>

      <table class="mini">
        <thead>
          <tr><th></th><th>{{ $t('analytics.received') }}</th><th>{{ $t('analytics.given') }}</th></tr>
        </thead>
        <tbody>
          <tr v-for="k in INTERACTION_KINDS" :key="k">
            <td><span class="sw" :style="{ background: CATEGORY_COLOR[k] }"></span>{{ $t(`analytics.categories.${k}`) }}</td>
            <td>{{ fmt(agent.received[k]) }}</td>
            <td>{{ fmt(agent.given[k]) }}</td>
          </tr>
          <tr>
            <td><span class="sw" :style="{ background: CATEGORY_COLOR.post }"></span>{{ $t('analytics.categories.post') }}</td>
            <td>–</td>
            <td>{{ fmt(agent.given.post) }}</td>
          </tr>
        </tbody>
      </table>

      <div class="conns">
        <div>
          <h4>{{ $t('analytics.engagedBy') }}</h4>
          <ul>
            <li v-for="c in inbound" :key="c.name" @click="emit('update:selected', c.name)">
              <span class="cname">{{ c.name }}</span>
              <span class="ckinds">
                <span v-for="k in INTERACTION_KINDS" v-show="c[k]" :key="k"><span class="sw" :style="{ background: CATEGORY_COLOR[k] }"></span>{{ c[k] }}</span>
              </span>
            </li>
            <li v-if="!inbound.length" class="none">–</li>
          </ul>
        </div>
        <div>
          <h4>{{ $t('analytics.engagedWith') }}</h4>
          <ul>
            <li v-for="c in outbound" :key="c.name" @click="emit('update:selected', c.name)">
              <span class="cname">{{ c.name }}</span>
              <span class="ckinds">
                <span v-for="k in INTERACTION_KINDS" v-show="c[k]" :key="k"><span class="sw" :style="{ background: CATEGORY_COLOR[k] }"></span>{{ c[k] }}</span>
              </span>
            </li>
            <li v-if="!outbound.length" class="none">–</li>
          </ul>
        </div>
      </div>
    </template>
    <p v-else class="hint">{{ $t('analytics.selectHint') }}</p>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { INTERACTION_KINDS, CATEGORY_COLOR, fmt, pct } from './palette'

const props = defineProps({
  agents: { type: Array, default: () => [] },
  edges: { type: Array, default: () => [] },
  selected: { type: String, default: null }
})
const emit = defineEmits(['update:selected'])

const agent = computed(() => props.agents.find(a => a.name === props.selected) || null)

const group = (key, other) => {
  const m = new Map()
  for (const e of props.edges) {
    if (e[key] !== props.selected) continue
    const name = e[other]
    const row = m.get(name) || { name, support: 0, oppose: 0, reply: 0, total: 0 }
    row[e.kind] += e.weight
    row.total += e.weight
    m.set(name, row)
  }
  return [...m.values()].sort((a, b) => b.total - a.total).slice(0, 6)
}
const inbound = computed(() => group('target', 'source'))
const outbound = computed(() => group('source', 'target'))
</script>

<style scoped>
.eyebrow { font-family: var(--hm-font-mono); font-size: 10px; letter-spacing: 0.08em; text-transform: uppercase; color: var(--hm-ink-4); margin: 0 0 2px; }
.agent-name { word-break: break-word; }
.stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin: 4px 0 14px; }
.stats div { display: flex; flex-direction: column; gap: 2px; }
.stats strong { font-size: 18px; color: var(--hm-ink); font-weight: 600; }
.stats span { font-size: 11px; color: var(--hm-ink-3); }
table.mini { width: 100%; border-collapse: collapse; font-size: 12px; margin-bottom: 14px; }
table.mini th { text-align: right; font-weight: 500; color: var(--hm-ink-4); font-size: 11px; padding: 4px 6px; border-bottom: 1px solid var(--hm-line); }
table.mini td { text-align: right; padding: 5px 6px; color: var(--hm-ink); font-variant-numeric: tabular-nums; border-bottom: 1px solid var(--hm-surface-3); }
table.mini td:first-child, table.mini th:first-child { text-align: left; color: var(--hm-ink-3); }
table.mini .sw { margin-right: 6px; }
.conns { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.conns h4 { font-size: 11px; font-weight: 600; color: var(--hm-ink-3); margin: 0 0 6px; text-transform: uppercase; letter-spacing: 0.05em; }
.conns ul { list-style: none; margin: 0; padding: 0; }
.conns li { display: flex; justify-content: space-between; gap: 6px; font-size: 12px; padding: 4px 0; cursor: pointer; border-bottom: 1px solid var(--hm-surface-3); }
.conns li:hover .cname { text-decoration: underline; }
.conns li.none { color: #b0afa8; cursor: default; }
.cname { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; color: var(--hm-ink); }
.ckinds { display: flex; gap: 6px; color: var(--hm-ink-3); font-variant-numeric: tabular-nums; flex-shrink: 0; }
.ckinds .sw { margin-right: 3px; }
.hint { color: var(--hm-ink-4); font-size: 13px; margin: 0; line-height: 1.5; }
</style>
