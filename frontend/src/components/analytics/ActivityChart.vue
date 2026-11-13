<template>
  <section class="card">
    <header class="card-head">
      <div>
        <h3>{{ $t('analytics.activityTitle') }}</h3>
        <p class="sub">{{ $t('analytics.activitySubtitle') }}</p>
      </div>
      <div class="seg-toggle">
        <button :class="{ on: !showTable }" @click="showTable = false">{{ $t('analytics.showChart') }}</button>
        <button :class="{ on: showTable }" @click="showTable = true">{{ $t('analytics.showTable') }}</button>
      </div>
    </header>

    <ul class="legend">
      <li v-for="c in CATEGORY_ORDER" :key="c" :title="$t(`analytics.categoryHints.${c}`)">
        <span class="sw" :style="{ background: CATEGORY_COLOR[c] }"></span>{{ $t(`analytics.categories.${c}`) }}
      </li>
    </ul>

    <div v-show="!showTable" class="plot" ref="plotEl" @pointerleave="hover = null">
      <svg :width="width" :height="HEIGHT" role="img" :aria-label="$t('analytics.activityTitle')">
        <g :transform="`translate(${M.left},${M.top})`">
          <g class="grid">
            <g v-for="tk in yTicks" :key="tk" :transform="`translate(0,${y(tk)})`">
              <line :x2="innerW" />
              <text x="-8" dy="0.32em" text-anchor="end">{{ fmt(tk) }}</text>
            </g>
          </g>
          <rect v-if="hover !== null" class="band"
            :x="x(hover) - x.step() * x.paddingInner() / 2" :width="x.step()" :height="innerH" />
          <g v-for="s in stacks" :key="s.round">
            <path v-for="seg in s.segs" :key="seg.cat" :d="seg.d" :fill="CATEGORY_COLOR[seg.cat]" />
          </g>
          <line class="baseline" :y1="innerH" :y2="innerH" :x2="innerW" />
          <g class="xaxis" :transform="`translate(0,${innerH})`">
            <text v-for="r in xTicks" :key="r" :x="x(r) + x.bandwidth() / 2" y="16" text-anchor="middle">{{ r }}</text>
            <text :x="innerW" y="32" text-anchor="end" class="axis-title">{{ $t('analytics.round') }}</text>
          </g>
          <rect v-for="r in roundsIdx" :key="`hit-${r}`" class="hit"
            :x="x(r) - x.step() * x.paddingInner() / 2" :width="x.step()" :height="innerH"
            @pointerenter="hover = r" @focus="hover = r" tabindex="-1" />
        </g>
      </svg>
      <div v-if="hoverRow" class="tip" :style="tipStyle">
        <div class="tip-title">{{ $t('analytics.round') }} {{ hoverRow.round }}</div>
        <div v-for="c in [...CATEGORY_ORDER].reverse()" :key="c" class="tip-row">
          <span class="sw" :style="{ background: CATEGORY_COLOR[c] }"></span>
          <strong>{{ fmt(hoverRow[c]) }}</strong><span>{{ $t(`analytics.categories.${c}`) }}</span>
        </div>
        <div class="tip-row total"><strong>{{ fmt(hoverRow.total) }}</strong><span>{{ $t('analytics.total') }}</span></div>
        <div class="tip-row"><strong>{{ fmt(hoverRow.active_agents) }}</strong><span>{{ $t('analytics.activeAgents') }}</span></div>
      </div>
    </div>

    <div v-if="showTable" class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>{{ $t('analytics.round') }}</th>
            <th v-for="c in CATEGORY_ORDER" :key="c">{{ $t(`analytics.categories.${c}`) }}</th>
            <th>{{ $t('analytics.total') }}</th>
            <th>{{ $t('analytics.activeAgents') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in rounds" :key="r.round">
            <td>{{ r.round }}</td>
            <td v-for="c in CATEGORY_ORDER" :key="c">{{ fmt(r[c]) }}</td>
            <td><strong>{{ fmt(r.total) }}</strong></td>
            <td>{{ fmt(r.active_agents) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import * as d3 from 'd3'
import { CATEGORY_ORDER, CATEGORY_COLOR, fmt } from './palette'

const props = defineProps({
  rounds: { type: Array, default: () => [] }
})

const HEIGHT = 240
const M = { top: 8, right: 8, bottom: 40, left: 44 }
const GAP = 2 // surface gap between stacked segments
const RADIUS = 3

const plotEl = ref(null)
const width = ref(800)
const showTable = ref(false)
const hover = ref(null)

let ro = null
onMounted(() => {
  ro = new ResizeObserver(([entry]) => { width.value = Math.max(320, entry.contentRect.width) })
  if (plotEl.value) ro.observe(plotEl.value)
})
onUnmounted(() => ro && ro.disconnect())

const innerW = computed(() => width.value - M.left - M.right)
const innerH = HEIGHT - M.top - M.bottom
const roundsIdx = computed(() => props.rounds.map(r => r.round))

const x = computed(() => d3.scaleBand()
  .domain(roundsIdx.value)
  .range([0, innerW.value])
  .paddingInner(props.rounds.length > 60 ? 0.15 : 0.3)
  .paddingOuter(0.1))

const maxTotal = computed(() => d3.max(props.rounds, r => r.total) || 1)
const y = computed(() => d3.scaleLinear().domain([0, maxTotal.value]).nice(4).range([innerH, 0]))
const yTicks = computed(() => y.value.ticks(4))

const xTicks = computed(() => {
  const n = props.rounds.length
  const every = Math.max(1, Math.ceil(n / Math.max(2, Math.floor(innerW.value / 48))))
  return roundsIdx.value.filter(r => r % every === 0)
})

// Rect with only its top corners rounded (data end), flat on the baseline side.
const topRounded = (x0, y0, w, h, r) => {
  r = Math.min(r, w / 2, h)
  return `M${x0},${y0 + h}V${y0 + r}Q${x0},${y0} ${x0 + r},${y0}H${x0 + w - r}Q${x0 + w},${y0} ${x0 + w},${y0 + r}V${y0 + h}Z`
}

const stacks = computed(() => props.rounds.map(row => {
  const bx = x.value(row.round)
  const bw = x.value.bandwidth()
  const present = CATEGORY_ORDER.filter(c => row[c] > 0)
  let acc = 0
  const segs = present.map((c, i) => {
    const y0 = y.value(acc + row[c])
    const y1 = y.value(acc)
    acc += row[c]
    const isTop = i === present.length - 1
    const h = Math.max(0, y1 - y0 - (isTop ? 0 : GAP))
    const d = isTop ? topRounded(bx, y0, bw, h, RADIUS) : `M${bx},${y0 + GAP}h${bw}v${h}h${-bw}Z`
    return { cat: c, d }
  })
  return { round: row.round, segs }
}))

const hoverRow = computed(() => (hover.value === null ? null : props.rounds.find(r => r.round === hover.value)))
const tipStyle = computed(() => {
  if (hover.value === null) return {}
  const cx = M.left + x.value(hover.value) + x.value.bandwidth() / 2
  const flip = cx > width.value - 200
  return { left: `${flip ? cx - 12 : cx + 12}px`, transform: flip ? 'translateX(-100%)' : 'none' }
})
</script>

<style scoped>
.plot { position: relative; }
svg { display: block; overflow: visible; font-family: Inter, system-ui, sans-serif; }
.grid line { stroke: #eeeeec; }
.grid text, .xaxis text { fill: #898781; font-size: 11px; font-variant-numeric: tabular-nums; }
.axis-title { font-size: 10px; text-transform: uppercase; letter-spacing: 0.06em; }
.baseline { stroke: #c3c2b7; }
.band { fill: #f4f4f2; }
.hit { fill: transparent; cursor: crosshair; outline: none; }
.tip { top: 8px; }
.tip-row.total { border-top: 1px solid #eee; margin-top: 4px; padding-top: 4px; }
</style>
