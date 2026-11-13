<template>
  <section class="card">
    <header class="card-head">
      <div>
        <h3>{{ $t('analytics.influencersTitle') }}</h3>
        <p class="sub">{{ $t('analytics.influencersSubtitle') }}</p>
      </div>
    </header>
    <ol class="rank">
      <li v-for="(a, i) in top" :key="a.name" :class="{ on: a.name === selected }"
        @click="emit('update:selected', a.name === selected ? null : a.name)"
        @pointerenter="hover = a.name" @pointerleave="hover = null">
        <span class="pos">{{ i + 1 }}</span>
        <div class="body">
          <div class="line1">
            <span class="name" :title="a.name">{{ a.name }}</span>
            <span class="val">{{ fmt(a.engagement_received) }}</span>
          </div>
          <div class="bar" :style="{ width: `${(a.engagement_received / maxVal) * 100}%` }">
            <template v-for="k in INTERACTION_KINDS" :key="k">
              <span v-if="a.received[k] > 0" class="seg"
                :style="{ flexGrow: a.received[k], background: CATEGORY_COLOR[k] }"></span>
            </template>
          </div>
          <div class="line2">
            <span :title="$t('analytics.reachHint')">{{ $t('analytics.reach') }} {{ fmt(a.reach) }}</span>
            <span :title="$t('analytics.kpiApprovalHint')">{{ $t('analytics.approval') }} {{ pct(a.approval) }}</span>
          </div>
          <div v-if="hover === a.name" class="mini-tip">
            <span v-for="k in INTERACTION_KINDS" :key="k">
              <span class="sw" :style="{ background: CATEGORY_COLOR[k] }"></span>
              <strong>{{ fmt(a.received[k]) }}</strong> {{ $t(`analytics.categories.${k}`) }}
            </span>
          </div>
        </div>
      </li>
    </ol>
  </section>
</template>

<script setup>
import { ref, computed } from 'vue'
import { INTERACTION_KINDS, CATEGORY_COLOR, fmt, pct } from './palette'

const props = defineProps({
  agents: { type: Array, default: () => [] },
  selected: { type: String, default: null },
  limit: { type: Number, default: 10 }
})
const emit = defineEmits(['update:selected'])
const hover = ref(null)

const top = computed(() => props.agents.filter(a => a.engagement_received > 0).slice(0, props.limit))
const maxVal = computed(() => Math.max(1, ...top.value.map(a => a.engagement_received)))
</script>

<style scoped>
.rank { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 4px; }
.rank li {
  display: flex; gap: 10px; align-items: flex-start; padding: 8px; border-radius: 6px; cursor: pointer;
  border: 1px solid transparent;
}
.rank li:hover { background: #f7f7f5; }
.rank li.on { border-color: var(--hm-ink); background: var(--hm-surface-2); }
.pos { font-family: var(--hm-font-mono); font-size: 11px; color: var(--hm-ink-4); width: 18px; padding-top: 2px; }
.body { flex: 1; min-width: 0; }
.line1 { display: flex; justify-content: space-between; gap: 8px; font-size: 13px; }
.name { color: var(--hm-ink); font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.val { color: var(--hm-ink); font-weight: 600; font-variant-numeric: tabular-nums; }
.bar { display: flex; gap: 2px; height: 8px; margin: 5px 0 4px; min-width: 6px; }
.seg { height: 100%; min-width: 2px; }
.seg:last-child { border-radius: 0 4px 4px 0; }
.line2 { display: flex; gap: 14px; font-size: 11px; color: var(--hm-ink-3); font-variant-numeric: tabular-nums; }
.mini-tip { display: flex; gap: 12px; flex-wrap: wrap; margin-top: 6px; font-size: 11px; color: var(--hm-ink-3); }
.mini-tip strong { color: var(--hm-ink); }
.mini-tip .sw { margin-right: 4px; }
</style>
