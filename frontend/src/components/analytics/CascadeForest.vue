<template>
  <section class="card cascade-card">
    <header class="card-head">
      <div>
        <h3>{{ $t('analytics.cascadesTitle') }}</h3>
        <p class="sub">{{ $t('analytics.cascadesSubtitle') }}</p>
      </div>
      <ul class="legend shape-legend">
        <li><span class="sw orphan" />{{ $t('analytics.shapeOrphan') }}</li>
        <li><span class="sw broadcast" />{{ $t('analytics.shapeBroadcast') }}</li>
        <li><span class="sw chain" />{{ $t('analytics.shapeChain') }}</li>
      </ul>
    </header>

    <div v-if="!cascades.length" class="empty">{{ $t('analytics.cascadesEmpty') }}</div>

    <div v-else class="forest">
      <button
        v-for="c in cascades"
        :key="`${c.platform}-${c.root_id}`"
        class="cascade"
        :class="[c.shape, { selected: selectedId === c.root_id }]"
        @click="selectedId = selectedId === c.root_id ? null : c.root_id"
      >
        <div class="cascade-meta">
          <span class="platform">{{ platformLabel(c.platform) }}</span>
          <span class="shape-tag">{{ shapeLabel(c.shape) }}</span>
          <span class="stats">
            size {{ c.size }} · depth {{ c.depth }} · ν {{ c.virality }}
          </span>
        </div>
        <div class="author">{{ c.root_author }}</div>
        <p class="snippet">“{{ truncate(c.root_content) }}”</p>
        <svg class="tree-svg" :viewBox="`0 0 ${svgW} ${svgH(c)}`" :height="svgH(c)">
          <g v-for="(edge, i) in layout(c).edges" :key="`e-${i}`">
            <line :x1="edge.x1" :y1="edge.y1" :x2="edge.x2" :y2="edge.y2"
              class="edge" :class="c.shape" />
          </g>
          <g v-for="(n, i) in layout(c).nodes" :key="`n-${i}`">
            <circle :cx="n.x" :cy="n.y" :r="n.root ? 7 : 5"
              class="node" :class="[c.shape, n.kind]" />
            <title>{{ n.author }} ({{ n.kind }})</title>
          </g>
        </svg>
      </button>
    </div>

    <div v-if="selected" class="detail">
      <div class="tip-title">{{ selected.root_author }} · {{ shapeLabel(selected.shape) }}</div>
      <p class="snippet">{{ selected.root_content }}</p>
      <div class="tip-row"><strong>{{ selected.size }}</strong><span>{{ $t('analytics.cascadeSize') }}</span></div>
      <div class="tip-row"><strong>{{ selected.depth }}</strong><span>{{ $t('analytics.cascadeDepth') }}</span></div>
      <div class="tip-row"><strong>{{ selected.virality }}</strong><span>{{ $t('analytics.cascadeVirality') }}</span></div>
      <p class="explain">{{ shapeExplain(selected) }}</p>
    </div>
  </section>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps({
  cascades: { type: Array, default: () => [] }
})
const { t } = useI18n()
const selectedId = ref(null)
const selected = computed(() => props.cascades.find(c => c.root_id === selectedId.value) || null)

const svgW = 280

const truncate = (s) => {
  const t = (s || '').replace(/\s+/g, ' ').trim()
  return t.length > 110 ? `${t.slice(0, 110)}…` : t
}

const platformLabel = (p) => t(`analytics.platforms.${p}`) || p
const shapeLabel = (s) => t(`analytics.shape${s.charAt(0).toUpperCase()}${s.slice(1)}`) || s

const shapeExplain = (c) => {
  if (c.shape === 'orphan') return t('analytics.shapeOrphanHint')
  if (c.shape === 'broadcast') return t('analytics.shapeBroadcastHint')
  return t('analytics.shapeChainHint')
}

const svgH = (c) => Math.max(48, 28 + (c.depth + 1) * 28)

/** Simple layered tree layout from the nested `tree` payload. */
const layout = (c) => {
  const root = c.tree
  if (!root) return { nodes: [], edges: [] }
  const levels = []
  const walk = (n, depth) => {
    if (!levels[depth]) levels[depth] = []
    levels[depth].push(n)
    for (const ch of n.children || []) walk(ch, depth + 1)
  }
  walk(root, 0)

  const nodes = []
  const pos = new Map()
  levels.forEach((row, depth) => {
    const y = 16 + depth * 28
    row.forEach((n, i) => {
      const x = ((i + 1) / (row.length + 1)) * svgW
      pos.set(n, { x, y })
      nodes.push({
        x, y,
        author: n.author,
        kind: n.kind,
        root: depth === 0
      })
    })
  })

  const edges = []
  const link = (n) => {
    const p = pos.get(n)
    for (const ch of n.children || []) {
      const q = pos.get(ch)
      if (p && q) edges.push({ x1: p.x, y1: p.y, x2: q.x, y2: q.y })
      link(ch)
    }
  }
  link(root)
  return { nodes, edges }
}
</script>

<style scoped>
.forest {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 12px;
}
.cascade {
  text-align: left;
  background: var(--hm-surface-2);
  border: 1px solid var(--hm-line);
  border-radius: var(--hm-radius-md);
  padding: 12px 14px 8px;
  cursor: pointer;
  font: inherit;
  color: inherit;
}
.cascade:hover, .cascade.selected { border-color: var(--hm-ink-5); background: var(--hm-surface); }
.cascade.orphan { border-top: 3px solid #c3c2b7; }
.cascade.broadcast { border-top: 3px solid #2a78d6; }
.cascade.chain { border-top: 3px solid #1baf7a; }
.cascade-meta { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-bottom: 6px; }
.platform, .shape-tag, .stats {
  font-family: var(--hm-font-mono); font-size: 10px; letter-spacing: 0.04em; text-transform: uppercase;
  color: var(--hm-ink-4);
}
.shape-tag { color: var(--hm-ink-2); }
.author { font-weight: 600; font-size: 13px; color: var(--hm-ink); }
.snippet { margin: 4px 0 8px; font-size: 12px; color: var(--hm-ink-3); line-height: 1.45; }
.tree-svg { width: 100%; display: block; }
.edge { stroke: #c3c2b7; stroke-width: 1.4; }
.edge.broadcast { stroke: #2a78d6; }
.edge.chain { stroke: #1baf7a; }
.node { fill: #c3c2b7; stroke: #fff; stroke-width: 1.5; }
.node.broadcast, .node.original.broadcast { fill: #2a78d6; }
.cascade.broadcast .node { fill: #2a78d6; }
.cascade.chain .node { fill: #1baf7a; }
.cascade.orphan .node { fill: #898781; }
.node.comment { fill: #eda100; }
.shape-legend .sw { width: 10px; height: 10px; border-radius: 2px; }
.sw.orphan { background: #c3c2b7; }
.sw.broadcast { background: #2a78d6; }
.sw.chain { background: #1baf7a; }
.empty { font-size: 13px; color: var(--hm-ink-4); padding: 8px 0; }
.detail {
  margin-top: 14px; padding: 12px 14px; border: 1px solid var(--hm-line);
  border-radius: var(--hm-radius-md); background: var(--hm-surface-2);
}
.tip-title { font-weight: 600; margin-bottom: 4px; }
.tip-row { display: flex; gap: 8px; font-size: 12px; color: var(--hm-ink-3); line-height: 1.7; }
.tip-row strong { min-width: 36px; text-align: right; color: var(--hm-ink); font-variant-numeric: tabular-nums; }
.explain { margin: 8px 0 0; font-size: 13px; color: var(--hm-ink-2); }
</style>
