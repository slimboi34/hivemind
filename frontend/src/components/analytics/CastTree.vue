<template>
  <section class="card cast-card" aria-labelledby="cast-title">
    <header class="card-head">
      <div>
        <h3 id="cast-title">{{ $t('analytics.castTitle') }}</h3>
        <p class="sub">{{ $t('analytics.castSubtitle') }}</p>
      </div>
      <span v-if="cast?.total" class="progress" :class="{ done: cast.complete }">
        <span class="progress-dot"></span>
        {{ cast.complete ? $t('analytics.castReady', { n: cast.total }) : $t('analytics.castProgress', { ready: cast.ready, total: cast.total }) }}
      </span>
    </header>

    <p v-if="!cast?.total" class="empty">{{ $t('analytics.castEmpty') }}</p>

    <template v-else>
      <ul class="legend">
        <li v-for="g in cast.groups" :key="g.key">
          <button class="group-toggle" :class="{ off: focus && focus !== g.key }" @click="focus = focus === g.key ? null : g.key">
            <span class="sw" :style="{ background: GROUP_COLOR[g.key] }"></span>{{ g.label }}
            <span class="count">{{ g.ready < g.count ? `${g.ready}/${g.count}` : g.count }}</span>
          </button>
        </li>
      </ul>
      <ul v-if="added" class="origins">
        <li><svg width="12" height="12"><circle cx="6" cy="6" r="4.5" class="k-evidence" /></svg>{{ $t('analytics.castOriginEvidence') }} <span class="count">{{ cast.origins.evidence }}</span></li>
        <li v-if="cast.origins.circle"><svg width="12" height="12"><circle cx="6" cy="6" r="3.5" class="k-circle" /></svg>{{ $t('analytics.castOriginCircle') }} <span class="count">{{ cast.origins.circle }}</span></li>
        <li v-if="cast.origins.joined"><svg width="12" height="12"><path :d="DIAMOND" transform="translate(6,6)" class="k-joined" /></svg>{{ $t('analytics.castOriginJoined') }} <span class="count">{{ cast.origins.joined }}</span></li>
        <li v-if="cast.growing" class="growing"><span class="progress-dot"></span>{{ $t('analytics.castGrowing') }}</li>
      </ul>

      <div class="stage" ref="stageEl" @pointerleave="hover = null">
        <svg :width="width" :height="height" role="img" :aria-label="$t('analytics.castAria', { n: cast.total })">
          <g :transform="`translate(${width / 2},${height / 2})`">
            <path v-for="l in links" :key="l.key" :d="l.d" class="link"
              :stroke="l.color" :stroke-opacity="l.opacity" :stroke-width="l.w" :stroke-dasharray="l.dash" fill="none" />

            <g v-for="n in branches" :key="n.key" :transform="n.t" :opacity="n.opacity">
              <circle :r="n.r" :fill="n.color" />
              <text v-if="n.label" :transform="n.textT" :text-anchor="n.anchor" dy="0.32em" :dx="n.dx" class="branch-label" :class="n.cls">{{ n.label }}</text>
            </g>

            <g v-for="n in leaves" :key="n.key" :transform="n.t" :opacity="n.opacity" class="leaf"
              :class="[n.agent.origin, { pending: !n.agent.ready, selected: n.agent.name === selected }]"
              @pointerenter="hover = n" @click="emit('update:selected', n.agent.name === selected ? null : n.agent.name)">
              <path v-if="n.agent.origin === 'joined'" :d="DIAMOND" :fill="n.color" stroke="var(--hm-ink)" />
              <circle v-else :r="n.r" :fill="n.agent.ready ? n.color : 'var(--hm-surface)'" :stroke="n.color" />
              <text :transform="n.textT" :text-anchor="n.anchor" dy="0.32em" :dx="n.dx" :style="{ fontSize: leafFont + 'px' }">{{ n.short }}</text>
            </g>

            <g class="hub">
              <circle r="34" />
              <text class="hub-n" dy="-0.1em" text-anchor="middle">{{ cast.complete ? cast.total : cast.ready }}</text>
              <text class="hub-l" dy="1.5em" text-anchor="middle">{{ cast.complete ? $t('analytics.castAgents') : `/ ${cast.total}` }}</text>
            </g>
          </g>
        </svg>

        <div v-if="hover" class="tip" :style="tipStyle">
          <div class="tip-title">{{ hover.agent.name }}</div>
          <div class="tip-line">{{ hover.typeLabel }} · {{ hover.groupLabel }}</div>
          <div v-if="hover.agent.anchor" class="tip-line tip-tie">{{ hover.agent.relation ? `${cap(hover.agent.relation)} ${hover.agent.anchor}` : $t('analytics.castAround', { name: hover.agent.anchor }) }}</div>
          <div v-if="hover.agent.profession" class="tip-line">{{ hover.agent.profession }}</div>
          <div v-if="hover.agent.stance" class="tip-line">{{ $t('analytics.castStance') }} {{ hover.agent.stance }}</div>
          <div v-if="hover.agent.bio" class="tip-bio">{{ hover.agent.bio }}</div>
          <div v-if="hover.agent.joined_round" class="tip-line tip-tie">{{ $t('analytics.castJoinedRound', { n: hover.agent.joined_round }) }}</div>
          <div v-if="hover.agent.why" class="tip-bio">{{ hover.agent.why }}</div>
          <div v-if="hover.agent.origin !== 'evidence'" class="tip-line added-note">{{ $t('analytics.castAdded') }}</div>
          <div v-if="!hover.agent.ready" class="tip-line pending-note">{{ $t('analytics.castPending') }}</div>
        </div>
      </div>
    </template>
  </section>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import * as d3 from 'd3'
import { getSimulationCast } from '../../api/simulation'
import { GROUP_COLOR } from './palette'

const props = defineProps({
  simulationId: { type: String, required: true },
  selected: { type: String, default: null },
  // Keep polling until every persona is written (agent setup). Finished runs load once.
  live: { type: Boolean, default: true }
})
const emit = defineEmits(['update:selected', 'loaded'])

const POLL_MS = 2000
const GROWING_POLL_MS = 5000
const DIAMOND = 'M0,-5.5L5.5,0L0,5.5L-5.5,0Z'
const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1)
const cast = ref(null)
const focus = ref(null)
const hover = ref(null)
const stageEl = ref(null)
const width = ref(900)
let timer = null
let observer = null

const leafCount = computed(() => cast.value?.total || 0)
const added = computed(() => (cast.value?.origins?.circle || 0) + (cast.value?.origins?.joined || 0))
// Room for the labels grows with the cast; the ring never gets so tight that names collide.
const height = computed(() => Math.round(Math.min(Math.max(640, leafCount.value * 9 + 300), 860)))
const leafFont = computed(() => (leafCount.value > 110 ? 8.5 : leafCount.value > 70 ? 9.5 : 11))
const LABEL_ROOM = 135
const radius = computed(() => Math.max(120, Math.min(width.value, height.value) / 2 - LABEL_ROOM))

const root = computed(() => {
  if (!cast.value?.total) return null
  const data = {
    children: cast.value.groups.map(g => ({
      group: g,
      children: g.types.map(t => ({
        group: g,
        type: t,
        // An actor with people around it becomes a small fork: itself first, then its circle.
        children: t.agents.map(a => (a.circle?.length
          ? { group: g, type: t, children: [a, ...a.circle].map(m => ({ group: g, type: t, agent: m })) }
          : { group: g, type: t, agent: a }))
      }))
    }))
  }
  const h = d3.hierarchy(data)
  d3.cluster().size([2 * Math.PI, radius.value]).separation((a, b) => (a.parent === b.parent ? 1 : 2.2))(h)
  // Pull the group and type rings inwards so the three levels read as rings.
  h.each(n => {
    n.y = n.children ? [0, radius.value * 0.36, radius.value * 0.68, radius.value * 0.88][n.depth] : radius.value
  })
  return h
})

const polar = (n) => `rotate(${(n.x * 180) / Math.PI - 90}) translate(${n.y},0)`
const flipped = (n) => n.x >= Math.PI
const dim = (key) => (focus.value && focus.value !== key ? 0.12 : 1)
const clip = (s, n) => (s.length > n ? s.slice(0, n - 1) + '…' : s)

const links = computed(() => {
  if (!root.value) return []
  const gen = d3.linkRadial().angle(d => d.x).radius(d => d.y)
  return root.value.links().map((l, i) => {
    const g = l.target.data.group
    const ready = l.target.data.agent ? l.target.data.agent.ready : true
    return {
      key: i,
      d: gen(l),
      color: GROUP_COLOR[g.key],
      w: l.target.depth === 1 ? 2 : l.target.depth === 2 ? 1.4 : 1,
      dash: l.target.data.agent && l.target.data.agent.origin !== 'evidence' ? '3 3' : null,
      opacity: dim(g.key) * (ready ? 0.55 : 0.18)
    }
  })
})

const branches = computed(() => {
  if (!root.value) return []
  return root.value.descendants().filter(n => n.depth >= 1 && n.children).map((n, i) => {
    const g = n.data.group
    const isGroup = n.depth === 1
    const isFork = n.depth === 3
    // A type ring label only earns its place when the group has more than one type.
    // It is written inwards, so it may only be as long as the gap to the group ring.
    const room = Math.max(6, Math.floor((radius.value * 0.32 - 12) / 5.2))
    const label = isGroup || isFork ? null : (g.types.length > 1 ? clip(n.data.type.label, Math.min(22, room)) : null)
    return {
      key: `${n.depth}-${i}`,
      t: polar(n),
      r: isGroup ? 6 : isFork ? 2.2 : 3.5,
      color: GROUP_COLOR[g.key],
      opacity: dim(g.key),
      label,
      cls: isGroup ? 'group' : 'type',
      // Type names sit on the inner side of their node, where only one branch passes.
      anchor: flipped(n) ? 'start' : 'end',
      dx: flipped(n) ? 7 : -7,
      textT: flipped(n) ? 'rotate(180)' : null
    }
  })
})

const leaves = computed(() => {
  if (!root.value) return []
  const max = leafCount.value > 70 ? 22 : 24 // what fits in the label room outside the ring
  return root.value.leaves().map((n) => {
    const g = n.data.group
    return {
      key: n.data.agent.name,
      t: polar(n),
      x: n.x,
      y: n.y,
      r: n.data.agent.origin === 'circle' ? 3.5 : 4.5,
      color: GROUP_COLOR[g.key],
      opacity: dim(g.key),
      agent: n.data.agent,
      short: clip(n.data.agent.name, max),
      typeLabel: n.data.agent.type_label || n.data.type.label,
      groupLabel: g.label,
      anchor: flipped(n) ? 'end' : 'start',
      dx: flipped(n) ? -9 : 9,
      textT: flipped(n) ? 'rotate(180)' : null
    }
  })
})

const tipStyle = computed(() => {
  const n = hover.value
  if (!n) return {}
  const px = width.value / 2 + Math.cos(n.x - Math.PI / 2) * n.y
  const py = height.value / 2 + Math.sin(n.x - Math.PI / 2) * n.y
  const left = px > width.value / 2
  return {
    left: `${left ? px - 16 : px + 16}px`,
    top: `${Math.min(Math.max(8, py - 30), height.value - 150)}px`,
    transform: left ? 'translateX(-100%)' : 'none'
  }
})

const load = async () => {
  try {
    const res = await getSimulationCast(props.simulationId)
    cast.value = res.data
    emit('loaded', res.data)
  } catch (e) { /* the tree is a bonus view; the page works without it */ }
  clearTimeout(timer)
  // Keep looking while personas are being written, and while a run can still pull people in.
  if (props.live && !cast.value?.complete) timer = setTimeout(load, POLL_MS)
  else if (props.live && cast.value?.growing) timer = setTimeout(load, GROWING_POLL_MS)
}

watch(() => props.simulationId, load)
onMounted(() => {
  load()
  observer = new ResizeObserver(([entry]) => { width.value = Math.max(360, Math.round(entry.contentRect.width)) })
  if (stageEl.value) observer.observe(stageEl.value)
})
watch(stageEl, (el) => { if (el && observer) observer.observe(el) })
onUnmounted(() => { clearTimeout(timer); observer?.disconnect() })
</script>

<style scoped>
.progress {
  display: inline-flex; align-items: center; gap: 6px; font-family: var(--hm-font-mono); font-size: var(--hm-text-2xs);
  letter-spacing: 0.06em; text-transform: uppercase; color: var(--hm-ink-3); padding: 4px 10px;
  border-radius: var(--hm-radius-pill); background: var(--hm-surface-3); white-space: nowrap;
}
.progress-dot { width: 7px; height: 7px; border-radius: 50%; background: #eda100; animation: pulse 1.2s ease-in-out infinite; }
.progress.done .progress-dot { background: #1baf7a; animation: none; }
@keyframes pulse { 50% { opacity: 0.3; } }
.empty { margin: 0; font-size: var(--hm-text-sm); color: var(--hm-ink-3); }

.legend { margin-bottom: 4px; gap: 6px; }
.group-toggle {
  display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px; border: 1px solid var(--hm-line);
  border-radius: var(--hm-radius-pill); background: var(--hm-surface); font: inherit; font-size: 12px; color: var(--hm-ink); cursor: pointer;
}
.group-toggle:hover { border-color: var(--hm-ink-5); }
.group-toggle.off { opacity: 0.45; }
.count { color: var(--hm-ink-4); font-variant-numeric: tabular-nums; }

.origins {
  display: flex; flex-wrap: wrap; gap: 4px 16px; margin: 6px 0 0; padding: 0; list-style: none;
  font-size: 12px; color: var(--hm-ink-3);
}
.origins li { display: inline-flex; align-items: center; gap: 6px; }
.k-evidence { fill: var(--hm-ink-3); }
.k-circle { fill: var(--hm-ink-3); fill-opacity: 0.35; stroke: var(--hm-ink-3); stroke-width: 1.4px; }
.k-joined { fill: var(--hm-ink-3); stroke: var(--hm-ink); }
.growing { color: var(--hm-signal-ink); }

.stage { position: relative; width: 100%; overflow: hidden; }
svg { display: block; }
.link { transition: stroke-opacity 0.5s ease; }
.branch-label { font-size: 10px; fill: var(--hm-ink-3); paint-order: stroke; stroke: var(--hm-surface); stroke-width: 4px; stroke-linejoin: round; }
.leaf { cursor: pointer; transition: opacity 0.2s; }
.leaf circle { stroke-width: 1.6px; transition: fill 0.5s ease; }
.leaf text { fill: var(--hm-ink); }
.leaf.pending text { fill: var(--hm-ink-5); }
.leaf.circle circle { fill-opacity: 0.35; }
.leaf.circle text, .leaf.joined text { fill: var(--hm-ink-3); }
.leaf path { stroke-width: 1.2px; }
.leaf.pending circle { stroke-dasharray: 2 2; }
.leaf:hover text, .leaf.selected text { font-weight: 600; }
.leaf.selected circle { stroke: var(--hm-ink); stroke-width: 2.5px; }
.hub circle { fill: var(--hm-ink); }
.hub-n { fill: var(--hm-paper); font-family: var(--hm-font-display); font-size: 20px; font-weight: 500; }
.hub-l { fill: var(--hm-ink-5); font-family: var(--hm-font-mono); font-size: 8.5px; letter-spacing: 0.08em; text-transform: uppercase; }

.tip { max-width: 280px; }
.tip-line { line-height: 1.5; }
.tip-bio { margin-top: 6px; padding-top: 6px; border-top: 1px solid var(--hm-line); line-height: 1.45; color: var(--hm-ink-3); }
.pending-note { color: var(--hm-signal-ink); }
.tip-tie { font-weight: 600; }
.added-note { margin-top: 6px; color: var(--hm-ink-4); font-size: 11px; }
@media (prefers-reduced-motion: reduce) { .progress-dot { animation: none; } .link, .leaf circle { transition: none; } }
</style>
