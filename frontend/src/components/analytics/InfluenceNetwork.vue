<template>
  <section class="card network-card">
    <header class="card-head">
      <div>
        <h3>{{ $t('analytics.networkTitle') }}</h3>
        <p class="sub">{{ $t('analytics.networkSubtitle') }}</p>
      </div>
      <button class="ghost-btn" @click="fitView(true)">{{ $t('analytics.resetView') }}</button>
    </header>

    <div class="net-controls">
      <ul class="legend">
        <li v-for="k in INTERACTION_KINDS" :key="k">
          <button class="kind-toggle" :class="{ off: !enabled[k] }" :aria-pressed="enabled[k]"
            :title="$t(`analytics.categoryHints.${k}`)" @click="enabled[k] = !enabled[k]">
            <span class="sw line" :style="{ background: CATEGORY_COLOR[k] }"></span>{{ $t(`analytics.categories.${k}`) }}
          </button>
        </li>
      </ul>
      <div class="diverge-legend" :title="$t('analytics.kpiApprovalHint')">
        <span>{{ $t('analytics.categories.oppose') }}</span>
        <span class="ramp"></span>
        <span>{{ $t('analytics.categories.support') }}</span>
      </div>
    </div>

    <div class="stage" ref="stageEl" @pointerleave="hoverNode = null; hoverEdge = null">
      <svg ref="svgEl" :width="width" :height="HEIGHT" @click.self="emit('update:selected', null)">
        <defs>
          <marker v-for="k in INTERACTION_KINDS" :key="k" :id="`arrow-${uid}-${k}`" viewBox="0 0 10 10"
            refX="9" refY="5" markerWidth="7" markerHeight="7" markerUnits="userSpaceOnUse" orient="auto">
            <path d="M0,1 L9,5 L0,9 Z" :fill="CATEGORY_COLOR[k]" />
          </marker>
        </defs>
        <g>
          <g class="edges">
            <path v-for="e in drawnEdges" :key="e.key" :d="e.d"
              :stroke="CATEGORY_COLOR[e.kind]" :stroke-width="e.w" :stroke-opacity="e.opacity"
              :marker-end="e.arrow ? `url(#arrow-${uid}-${e.kind})` : null" fill="none" />
          </g>
          <g class="edge-hits">
            <path v-for="e in drawnEdges" :key="`h-${e.key}`" :d="e.d" class="edge-hit"
              @pointerenter="hoverEdge = e" @pointerleave="hoverEdge = null" />
          </g>
          <g class="nodes">
            <circle v-for="n in drawnNodes" :key="n.name" :cx="n.x" :cy="n.y" :r="n.r"
              :fill="n.fill" :fill-opacity="n.opacity" :stroke-opacity="n.opacity"
              :class="{ selected: n.name === selected, ghost: n.ghost }"
              @pointerenter="hoverNode = n" @pointerleave="hoverNode = null"
              @click.stop="emit('update:selected', n.name === selected ? null : n.name)" />
          </g>
          <g class="labels">
            <text v-for="n in labelledNodes" :key="`l-${n.name}`" :x="n.x" :y="n.y - n.r - 6"
              text-anchor="middle" :class="{ strong: n.name === selected }">{{ n.name }}</text>
          </g>
        </g>
      </svg>

      <div v-if="hoverNode && !hoverNode.ghost" class="tip" :style="tipAt(hoverNode)">
        <div class="tip-title">{{ hoverNode.name }}</div>
        <div v-for="k in INTERACTION_KINDS" :key="k" class="tip-row">
          <span class="sw" :style="{ background: CATEGORY_COLOR[k] }"></span>
          <strong>{{ fmt(hoverNode.recv[k]) }}</strong><span>{{ $t(`analytics.categories.${k}`) }} {{ $t('analytics.received').toLowerCase() }}</span>
        </div>
        <div class="tip-row total"><strong>{{ pct(hoverNode.approval) }}</strong><span>{{ $t('analytics.approval') }}</span></div>
        <div class="tip-row"><strong>{{ fmt(hoverNode.agent.reach) }}</strong><span>{{ $t('analytics.reach') }}</span></div>
        <div class="tip-row"><strong>{{ fmt(hoverNode.agent.actions) }}</strong><span>{{ $t('analytics.actions') }}</span></div>
      </div>
      <div v-else-if="hoverEdge" class="tip" :style="tipAt(hoverEdge.mid)">
        <div class="tip-title">{{ hoverEdge.source }} → {{ hoverEdge.target }}</div>
        <div class="tip-row">
          <span class="sw" :style="{ background: CATEGORY_COLOR[hoverEdge.kind] }"></span>
          <strong>{{ fmt(hoverEdge.weight) }}</strong><span>{{ $t(`analytics.categories.${hoverEdge.kind}`) }}</span>
        </div>
      </div>

      <div v-if="!edges.length" class="stage-empty">{{ $t('analytics.empty') }}</div>
    </div>

    <div class="replay">
      <button class="play-btn" :disabled="maxRound <= 0" @click="togglePlay">
        {{ playing ? $t('analytics.pause') : $t('analytics.play') }}
      </button>
      <input type="range" min="0" :max="maxRound" step="1" :value="cursor"
        :aria-label="$t('analytics.round')" @input="onScrub(+$event.target.value)" />
      <span class="replay-label">{{ $t('analytics.upToRound', { round: cursor, total: maxRound }) }}</span>
    </div>
  </section>
</template>

<script setup>
import { ref, reactive, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import * as d3 from 'd3'
import { INTERACTION_KINDS, CATEGORY_COLOR, fmt, pct } from './palette'

const props = defineProps({
  agents: { type: Array, default: () => [] },
  edges: { type: Array, default: () => [] },
  maxRound: { type: Number, default: 0 },
  selected: { type: String, default: null }
})
const emit = defineEmits(['update:selected'])

const HEIGHT = 560
const LABEL_COUNT = 10
const uid = Math.random().toString(36).slice(2, 8)

const stageEl = ref(null)
const svgEl = ref(null)
const width = ref(900)
const enabled = reactive({ support: true, oppose: true, reply: true })
const hoverNode = ref(null)
const hoverEdge = ref(null)
const cursor = ref(0)
const followLive = ref(true)
const playing = ref(false)
// Semantic zoom: the transform moves positions only, so nodes, labels and arrows keep their pixel size.
const transform = ref(d3.zoomIdentity)

// ---------- layout (stable across replay and live refreshes) ----------
const positions = ref(new Map()) // name -> {x, y}
let zoom = null

const fullEngagement = computed(() => {
  const m = new Map()
  for (const e of props.edges) m.set(e.target, (m.get(e.target) || 0) + e.weight)
  return m
})
const rScale = computed(() => d3.scaleSqrt()
  .domain([0, Math.max(1, ...fullEngagement.value.values())])
  .range([4, 24]))

const runLayout = () => {
  const prev = positions.value
  const nodes = props.agents.map(a => {
    const p = prev.get(a.name)
    return { name: a.name, x: p?.x, y: p?.y }
  })
  if (!nodes.length) { positions.value = new Map(); return }
  const pairs = new Map()
  for (const e of props.edges) {
    const key = [e.source, e.target].sort().join('\u0000')
    const cur = pairs.get(key) || { source: e.source, target: e.target, weight: 0 }
    cur.weight += e.weight
    pairs.set(key, cur)
  }
  const links = [...pairs.values()]
  const allKnown = nodes.every(n => n.x !== undefined)
  const maxPair = Math.max(1, ...links.map(l => l.weight))
  const sim = d3.forceSimulation(nodes)
    .force('link', d3.forceLink(links).id(d => d.name).distance(110)
      .strength(l => 0.04 + 0.5 * (l.weight / maxPair)))
    .force('charge', d3.forceManyBody().strength(-420).distanceMax(800))
    .force('x', d3.forceX(0).strength(0.015))
    .force('y', d3.forceY(0).strength(0.09))
    .force('collide', d3.forceCollide(d => rScale.value(fullEngagement.value.get(d.name) || 0) + 14))
    .stop()
  if (allKnown) sim.alpha(0.25)
  const ticks = allKnown ? 60 : 320
  for (let i = 0; i < ticks; i++) sim.tick()
  positions.value = new Map(nodes.map(n => [n.name, { x: n.x, y: n.y }]))
  if (!allKnown) nextTick(() => fitView(false))
}

let userZoomed = false
watch(width, () => { if (!userZoomed) fitView(false) })

const fitView = (animate) => {
  userZoomed = false
  if (!svgEl.value || !zoom || !positions.value.size) return
  const xs = [...positions.value.values()]
  const [x0, x1] = d3.extent(xs, p => p.x)
  const [y0, y1] = d3.extent(xs, p => p.y)
  const pad = 48 // screen px kept clear around the outermost nodes (room for labels and big nodes)
  const k = Math.min(4, (width.value - pad * 2) / Math.max(1, x1 - x0), (HEIGHT - pad * 2) / Math.max(1, y1 - y0))
  const t = d3.zoomIdentity.translate(width.value / 2, HEIGHT / 2).scale(k).translate(-(x0 + x1) / 2, -(y0 + y1) / 2)
  const sel = d3.select(svgEl.value)
  ;(animate ? sel.transition().duration(450) : sel).call(zoom.transform, t)
}

// ---------- state at the replay cursor ----------
const weightAt = (e, r) => {
  let w = 0
  for (const [k, v] of Object.entries(e.by_round)) if (+k <= r) w += v
  return w
}

const visibleEdges = computed(() => {
  const r = cursor.value
  const out = []
  for (const e of props.edges) {
    if (!enabled[e.kind] || e.first_round > r) continue
    const w = weightAt(e, r)
    if (w > 0) out.push({ ...e, weight: w })
  }
  return out
})

const nodeState = computed(() => {
  const r = cursor.value
  const recv = new Map()
  const touched = new Set()
  for (const e of visibleEdges.value) {
    const m = recv.get(e.target) || { support: 0, oppose: 0, reply: 0 }
    m[e.kind] += e.weight
    recv.set(e.target, m)
    touched.add(e.source)
    touched.add(e.target)
  }
  const out = new Map()
  for (const a of props.agents) {
    const m = recv.get(a.name) || { support: 0, oppose: 0, reply: 0 }
    const engagement = m.support + m.oppose + m.reply
    const polar = m.support + m.oppose
    out.set(a.name, {
      recv: m,
      engagement,
      approval: polar ? m.support / polar : null,
      active: touched.has(a.name) || (a.first_round !== null && a.first_round <= r)
    })
  }
  return out
})

const approvalColor = d3.scaleLinear()
  .domain([0, 0.5, 1])
  .range([CATEGORY_COLOR.oppose, '#b9b8b0', CATEGORY_COLOR.support])
  .interpolate(d3.interpolateLab)

const neighbours = computed(() => {
  if (!props.selected) return null
  const s = new Set([props.selected])
  for (const e of visibleEdges.value) {
    if (e.source === props.selected) s.add(e.target)
    if (e.target === props.selected) s.add(e.source)
  }
  return s
})

const drawnNodes = computed(() => {
  const nodes = []
  const t = transform.value
  for (const a of props.agents) {
    const p = positions.value.get(a.name)
    if (!p) continue
    const st = nodeState.value.get(a.name)
    const dim = neighbours.value && !neighbours.value.has(a.name)
    nodes.push({
      name: a.name,
      agent: a,
      x: t.applyX(p.x),
      y: t.applyY(p.y),
      r: st.active ? rScale.value(st.engagement) : 3,
      fill: st.approval === null ? '#b9b8b0' : approvalColor(st.approval),
      opacity: !st.active ? 0.18 : dim ? 0.15 : 1,
      ghost: !st.active,
      recv: st.recv,
      approval: st.approval,
      engagement: st.engagement
    })
  }
  // big nodes last so they sit on top
  return nodes.sort((a, b) => a.r - b.r)
})

const nodeByName = computed(() => new Map(drawnNodes.value.map(n => [n.name, n])))

const drawnEdges = computed(() => {
  const slot = new Map() // per directed pair: how many kinds already drawn
  const maxW = Math.max(1, ...visibleEdges.value.map(e => e.weight))
  return visibleEdges.value.map(e => {
    const s = nodeByName.value.get(e.source)
    const t = nodeByName.value.get(e.target)
    if (!s || !t) return null
    const dirKey = `${e.source}\u0000${e.target}`
    const i = slot.get(dirKey) || 0
    slot.set(dirKey, i + 1)
    const dx = t.x - s.x
    const dy = t.y - s.y
    const len = Math.hypot(dx, dy) || 1
    const ux = dx / len
    const uy = dy / len
    const bend = 10 + 12 * i // curve to the right of travel, so A→B and B→A separate
    const mx = (s.x + t.x) / 2 - uy * bend
    const my = (s.y + t.y) / 2 + ux * bend
    // shorten both ends to the node rims (approximate along the chord)
    const sx = s.x + ux * s.r
    const sy = s.y + uy * s.r
    const tx = t.x - ux * (t.r + 2)
    const ty = t.y - uy * (t.r + 2)
    const touchesSel = props.selected && (e.source === props.selected || e.target === props.selected)
    const strength = Math.sqrt(e.weight / maxW) // 0..1, one-off interactions recede, strong ties stand out
    return {
      key: `${dirKey}\u0000${e.kind}`,
      source: e.source,
      target: e.target,
      kind: e.kind,
      weight: e.weight,
      d: `M${sx},${sy}Q${mx},${my} ${tx},${ty}`,
      w: 1 + 2.5 * strength,
      arrow: props.selected ? touchesSel : strength >= 0.4,
      opacity: props.selected ? (touchesSel ? 0.9 : 0.04) : 0.12 + 0.68 * strength,
      mid: { x: mx, y: my, r: 0 }
    }
  }).filter(Boolean)
    // strongest drawn last so they sit on top
    .sort((a, b) => a.weight - b.weight)
})

// Selective direct labels: must-show names first (selected, hovered), then neighbours of the
// selection, then the most-engaged nodes; a label is skipped if it would overlap one already placed.
const labelledNodes = computed(() => {
  const active = drawnNodes.value.filter(n => !n.ghost)
  const byEngagement = [...active].sort((a, b) => b.engagement - a.engagement)
  const must = new Set([props.selected, hoverNode.value?.name].filter(Boolean))
  const nb = neighbours.value
  const ordered = [
    ...byEngagement.filter(n => must.has(n.name)),
    ...(nb ? byEngagement.filter(n => nb.has(n.name) && !must.has(n.name)) : []),
    ...byEngagement.filter(n => !must.has(n.name) && !(nb && nb.has(n.name))).slice(0, LABEL_COUNT)
  ]
  const placed = []
  const out = []
  for (const n of ordered) {
    const w = n.name.length * 6.4 + 6
    const box = { x0: n.x - w / 2, x1: n.x + w / 2, y0: n.y - n.r - 20, y1: n.y - n.r - 4 }
    const clash = placed.some(b => box.x0 < b.x1 && box.x1 > b.x0 && box.y0 < b.y1 && box.y1 > b.y0)
    if (clash && !must.has(n.name)) continue
    placed.push(box)
    out.push(n)
  }
  return out
})

const tipAt = (pt) => {
  const px = pt.x
  const py = pt.y
  const flip = px > width.value - 220
  return {
    left: `${flip ? px - 14 : px + 14}px`,
    top: `${Math.max(4, py - 20)}px`,
    transform: flip ? 'translateX(-100%)' : 'none'
  }
}

// ---------- replay ----------
let timer = null
const stop = () => { playing.value = false; clearInterval(timer); timer = null }
const togglePlay = () => {
  if (playing.value) return stop()
  if (cursor.value >= props.maxRound) cursor.value = 0
  followLive.value = false
  playing.value = true
  timer = setInterval(() => {
    if (cursor.value >= props.maxRound) { stop(); followLive.value = true; return }
    cursor.value += 1
  }, 650)
}
const onScrub = (v) => {
  stop()
  cursor.value = v
  followLive.value = v >= props.maxRound
}

watch(() => props.maxRound, (m) => {
  if (followLive.value || cursor.value > m) cursor.value = m
}, { immediate: true })

watch(() => [props.agents.length, props.edges.length], runLayout)

// ---------- mount ----------
let ro = null
onMounted(() => {
  zoom = d3.zoom().scaleExtent([0.05, 12]).on('zoom', (ev) => { transform.value = ev.transform; if (ev.sourceEvent) userZoomed = true })
  d3.select(svgEl.value).call(zoom).on('dblclick.zoom', null)
  ro = new ResizeObserver(([entry]) => { width.value = Math.max(320, entry.contentRect.width) })
  ro.observe(stageEl.value)
  runLayout()
  nextTick(() => fitView(false))
})
onUnmounted(() => { stop(); ro && ro.disconnect() })
</script>

<style scoped>
.stage { position: relative; border: 1px solid #f0f0ee; border-radius: 6px; background: #fff; overflow: hidden; }
svg { display: block; cursor: grab; font-family: Inter, system-ui, sans-serif; }
svg:active { cursor: grabbing; }
.nodes circle { stroke: #fff; stroke-width: 2px; cursor: pointer; transition: r 0.35s ease, fill 0.35s ease, fill-opacity 0.2s; }
.nodes circle.selected { stroke: #0b0b0b; stroke-width: 3px; }
.nodes circle.ghost { pointer-events: none; }
.edges path { transition: stroke-opacity 0.2s; pointer-events: none; }
.edge-hit { fill: none; stroke: transparent; stroke-width: 10px; cursor: help; }
.labels text {
  font-size: 11px; fill: #52514e; pointer-events: none;
  paint-order: stroke; stroke: #fff; stroke-width: 3px; stroke-linejoin: round;
}
.labels text.strong { fill: #0b0b0b; font-weight: 600; }
.stage-empty {
  position: absolute; inset: 0; display: flex; align-items: center; justify-content: center;
  color: #898781; font-size: 13px; padding: 40px; text-align: center; pointer-events: none;
}
.net-controls { display: flex; justify-content: space-between; align-items: center; gap: 16px; flex-wrap: wrap; margin-bottom: 10px; }
.net-controls .legend { margin: 0; }
.kind-toggle {
  display: inline-flex; align-items: center; gap: 6px; background: none; border: 1px solid #e6e6e3;
  border-radius: 999px; padding: 3px 10px; font: inherit; font-size: 12px; color: #0b0b0b; cursor: pointer;
}
.kind-toggle.off { color: #b0afa8; border-style: solid; background: #fafaf9; }
.kind-toggle.off .sw { opacity: 0.25; }
.sw.line { width: 14px; height: 3px; border-radius: 2px; }
.diverge-legend { display: flex; align-items: center; gap: 8px; font-size: 11px; color: #52514e; }
.ramp {
  width: 90px; height: 8px; border-radius: 4px;
  background: linear-gradient(90deg, #eb6834, #b9b8b0, #2a78d6);
}
.replay { display: flex; align-items: center; gap: 12px; margin-top: 12px; }
.replay input[type=range] { flex: 1; accent-color: #0b0b0b; }
.play-btn {
  min-width: 64px; padding: 6px 12px; border: none; border-radius: 4px; background: #0b0b0b; color: #fff;
  font-family: 'JetBrains Mono', monospace; font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; cursor: pointer;
}
.play-btn:disabled { opacity: 0.3; cursor: not-allowed; }
.replay-label { font-size: 12px; color: #52514e; font-variant-numeric: tabular-nums; min-width: 150px; text-align: right; }
</style>
