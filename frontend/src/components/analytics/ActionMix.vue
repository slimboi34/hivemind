<template>
  <section class="card">
    <header class="card-head">
      <div>
        <h3>{{ $t('analytics.mixTitle') }}</h3>
        <p class="sub">{{ $t('analytics.mixSubtitle') }}</p>
      </div>
    </header>
    <ul class="mix">
      <li v-for="row in rows" :key="row.type" :title="`${row.type}: ${fmt(row.count)} (${row.share})`">
        <span class="label">{{ row.type }}</span>
        <span class="track">
          <span class="fill" :style="{ width: `${(row.count / max) * 100}%`, background: CATEGORY_COLOR[row.cat] }"></span>
        </span>
        <span class="num">{{ fmt(row.count) }}</span>
      </li>
    </ul>
    <ul class="legend">
      <li v-for="c in usedCats" :key="c">
        <span class="sw" :style="{ background: CATEGORY_COLOR[c] }"></span>{{ $t(`analytics.categories.${c}`) }}
      </li>
    </ul>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { CATEGORY_ORDER, CATEGORY_COLOR, categoryOf, fmt } from './palette'

const props = defineProps({ actionTypes: { type: Object, default: () => ({}) } })

const total = computed(() => Object.values(props.actionTypes).reduce((s, v) => s + v, 0) || 1)
const rows = computed(() => Object.entries(props.actionTypes)
  .map(([type, count]) => ({ type, count, cat: categoryOf(type), share: `${Math.round((count / total.value) * 100)}%` }))
  .sort((a, b) => b.count - a.count))
const max = computed(() => Math.max(1, ...rows.value.map(r => r.count)))
const usedCats = computed(() => CATEGORY_ORDER.filter(c => rows.value.some(r => r.cat === c)))
</script>

<style scoped>
.mix { list-style: none; margin: 0 0 12px; padding: 0; display: flex; flex-direction: column; gap: 8px; }
.mix li { display: grid; grid-template-columns: 130px 1fr 48px; align-items: center; gap: 10px; }
.label { font-family: var(--hm-font-mono); font-size: 11px; color: var(--hm-ink-3); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.track { height: 10px; display: block; }
.fill { display: block; height: 100%; border-radius: 0 4px 4px 0; min-width: 2px; }
.num { text-align: right; font-size: 12px; color: var(--hm-ink); font-variant-numeric: tabular-nums; }
</style>
