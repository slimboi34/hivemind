<template>
  <div class="graph-panel">
    <div class="panel-header">
      <span class="panel-title">{{ $t('graph.panelTitle') }}</span>
      <!-- Top toolbar (Internal Top Right) -->
      <div class="header-tools">
        <button class="tool-btn" @click="$emit('refresh')" :disabled="loading" :title="$t('graph.refreshGraph')">
          <svg class="icon-refresh" :class="{ 'spinning': loading }" viewBox="0 0 16 16" width="14" height="14" aria-hidden="true"><path d="M13.25 8a5.25 5.25 0 1 1-1.54-3.71M13.25 2.75v2.5h-2.5" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
          <span class="btn-text">Refresh</span>
        </button>
        <button class="tool-btn icon-only" @click="$emit('toggle-maximize')" :title="$t('graph.toggleMaximize')" :aria-label="$t('graph.toggleMaximize')">
          <svg class="icon-maximize" viewBox="0 0 16 16" width="14" height="14" aria-hidden="true"><path d="M9.75 2.75h3.5v3.5M6.25 13.25h-3.5v-3.5M13.25 2.75 9 7M2.75 13.25 7 9" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
        </button>
      </div>
    </div>
    
    <div class="graph-container" ref="graphContainer">
      <!-- Graph visualisation -->
      <div v-if="graphData" class="graph-view">
        <svg ref="graphSvg" class="graph-svg"></svg>
        
        <!-- Building / simulating hint -->
        <div v-if="currentPhase === 1 || isSimulating" class="graph-building-hint">
          <div class="memory-icon-wrapper">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="memory-icon">
              <path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96.44 2.5 2.5 0 0 1-2.96-3.08 3 3 0 0 1-.34-5.58 2.5 2.5 0 0 1 1.32-4.24 2.5 2.5 0 0 1 4.44-4.04z" />
              <path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96.44 2.5 2.5 0 0 0 2.96-3.08 3 3 0 0 0 .34-5.58 2.5 2.5 0 0 0-1.32-4.24 2.5 2.5 0 0 0-4.44-4.04z" />
            </svg>
          </div>
          {{ isSimulating ? $t('graph.graphMemoryRealtime') : $t('graph.realtimeUpdating') }}
        </div>
        
        <!-- Hint shown after the simulation ends -->
        <div v-if="showSimulationFinishedHint" class="graph-building-hint finished-hint">
          <div class="hint-icon-wrapper">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="hint-icon">
              <circle cx="12" cy="12" r="10"></circle>
              <line x1="12" y1="16" x2="12" y2="12"></line>
              <line x1="12" y1="8" x2="12.01" y2="8"></line>
            </svg>
          </div>
          <span class="hint-text">{{ $t('graph.pendingContentHint') }}</span>
          <button class="hint-close-btn" @click="dismissFinishedHint" :title="$t('graph.closeHint')">
            <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>
        
        <!-- Node / edge detail panel -->
        <div v-if="selectedItem" class="detail-panel">
          <div class="detail-panel-header">
            <span class="detail-title">{{ selectedItem.type === 'node' ? $t('graph.nodeDetails') : $t('graph.relationship') }}</span>
            <span v-if="selectedItem.type === 'node'" class="detail-type-badge" :style="{ background: selectedItem.color, color: '#fff' }">
              {{ selectedItem.entityType }}
            </span>
            <button class="detail-close" aria-label="Close" @click="closeDetailPanel">
              <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true"><path d="M4 4l8 8M12 4l-8 8" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>
            </button>
          </div>
          
          <!-- Node details -->
          <div v-if="selectedItem.type === 'node'" class="detail-content">
            <div class="detail-row">
              <span class="detail-label">Name:</span>
              <span class="detail-value">{{ selectedItem.data.name }}</span>
            </div>
            <div class="detail-row">
              <span class="detail-label">UUID:</span>
              <span class="detail-value uuid-text">{{ selectedItem.data.uuid }}</span>
            </div>
            <div class="detail-row" v-if="selectedItem.data.created_at">
              <span class="detail-label">Created:</span>
              <span class="detail-value">{{ formatDateTime(selectedItem.data.created_at) }}</span>
            </div>
            
            <!-- Properties -->
            <div class="detail-section" v-if="selectedItem.data.attributes && Object.keys(selectedItem.data.attributes).length > 0">
              <div class="section-title">Properties:</div>
              <div class="properties-list">
                <div v-for="(value, key) in selectedItem.data.attributes" :key="key" class="property-item">
                  <span class="property-key">{{ key }}:</span>
                  <span class="property-value">{{ value || 'None' }}</span>
                </div>
              </div>
            </div>
            
            <!-- Summary -->
            <div class="detail-section" v-if="selectedItem.data.summary">
              <div class="section-title">Summary:</div>
              <div class="summary-text">{{ selectedItem.data.summary }}</div>
            </div>
            
            <!-- Labels -->
            <div class="detail-section" v-if="selectedItem.data.labels && selectedItem.data.labels.length > 0">
              <div class="section-title">Labels:</div>
              <div class="labels-list">
                <span v-for="label in selectedItem.data.labels" :key="label" class="label-tag">
                  {{ label }}
                </span>
              </div>
            </div>
          </div>
          
          <!-- Edge details -->
          <div v-else class="detail-content">
            <!-- Self-loop group details -->
            <template v-if="selectedItem.data.isSelfLoopGroup">
              <div class="edge-relation-header self-loop-header">
                {{ selectedItem.data.source_name }} - Self Relations
                <span class="self-loop-count">{{ selectedItem.data.selfLoopCount }} items</span>
              </div>
              
              <div class="self-loop-list">
                <div 
                  v-for="(loop, idx) in selectedItem.data.selfLoopEdges" 
                  :key="loop.uuid || idx" 
                  class="self-loop-item"
                  :class="{ expanded: expandedSelfLoops.has(loop.uuid || idx) }"
                >
                  <div 
                    class="self-loop-item-header"
                    @click="toggleSelfLoop(loop.uuid || idx)"
                  >
                    <span class="self-loop-index">#{{ idx + 1 }}</span>
                    <span class="self-loop-name">{{ loop.name || loop.fact_type || 'RELATED' }}</span>
                    <span class="self-loop-toggle">{{ expandedSelfLoops.has(loop.uuid || idx) ? '−' : '+' }}</span>
                  </div>
                  
                  <div class="self-loop-item-content" v-show="expandedSelfLoops.has(loop.uuid || idx)">
                    <div class="detail-row" v-if="loop.uuid">
                      <span class="detail-label">UUID:</span>
                      <span class="detail-value uuid-text">{{ loop.uuid }}</span>
                    </div>
                    <div class="detail-row" v-if="loop.fact">
                      <span class="detail-label">Fact:</span>
                      <span class="detail-value fact-text">{{ loop.fact }}</span>
                    </div>
                    <div class="detail-row" v-if="loop.fact_type">
                      <span class="detail-label">Type:</span>
                      <span class="detail-value">{{ loop.fact_type }}</span>
                    </div>
                    <div class="detail-row" v-if="loop.created_at">
                      <span class="detail-label">Created:</span>
                      <span class="detail-value">{{ formatDateTime(loop.created_at) }}</span>
                    </div>
                    <div v-if="loop.episodes && loop.episodes.length > 0" class="self-loop-episodes">
                      <span class="detail-label">Episodes:</span>
                      <div class="episodes-list compact">
                        <span v-for="ep in loop.episodes" :key="ep" class="episode-tag small">{{ ep }}</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </template>
            
            <!-- Regular edge details -->
            <template v-else>
              <div class="edge-relation-header">
                {{ selectedItem.data.source_name }} → {{ selectedItem.data.name || 'RELATED_TO' }} → {{ selectedItem.data.target_name }}
              </div>
              
              <div class="detail-row">
                <span class="detail-label">UUID:</span>
                <span class="detail-value uuid-text">{{ selectedItem.data.uuid }}</span>
              </div>
              <div class="detail-row">
                <span class="detail-label">Label:</span>
                <span class="detail-value">{{ selectedItem.data.name || 'RELATED_TO' }}</span>
              </div>
              <div class="detail-row">
                <span class="detail-label">Type:</span>
                <span class="detail-value">{{ selectedItem.data.fact_type || 'Unknown' }}</span>
              </div>
              <div class="detail-row" v-if="selectedItem.data.fact">
                <span class="detail-label">Fact:</span>
                <span class="detail-value fact-text">{{ selectedItem.data.fact }}</span>
              </div>
              
              <!-- Episodes -->
              <div class="detail-section" v-if="selectedItem.data.episodes && selectedItem.data.episodes.length > 0">
                <div class="section-title">Episodes:</div>
                <div class="episodes-list">
                  <span v-for="ep in selectedItem.data.episodes" :key="ep" class="episode-tag">
                    {{ ep }}
                  </span>
                </div>
              </div>
              
              <div class="detail-row" v-if="selectedItem.data.created_at">
                <span class="detail-label">Created:</span>
                <span class="detail-value">{{ formatDateTime(selectedItem.data.created_at) }}</span>
              </div>
              <div class="detail-row" v-if="selectedItem.data.valid_at">
                <span class="detail-label">Valid From:</span>
                <span class="detail-value">{{ formatDateTime(selectedItem.data.valid_at) }}</span>
              </div>
            </template>
          </div>
        </div>
      </div>
      
      <!-- Loading state -->
      <div v-else-if="loading" class="graph-state" role="status">
        <div class="loading-spinner"></div>
        <p>{{ $t('graph.graphDataLoading') }}</p>
      </div>
      
      <!-- Waiting / empty state -->
      <div v-else class="graph-state">
        <svg class="empty-icon" viewBox="0 0 32 32" width="44" height="44" aria-hidden="true">
          <path d="M10.8 3.5 15 5.9v4.8l-4.2 2.4-4.2-2.4V5.9z" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linejoin="round"/>
          <path d="M21.2 3.5 25.4 5.9v4.8l-4.2 2.4-4.2-2.4V5.9z" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linejoin="round"/>
          <path d="M16 12.5l4.2 2.4v4.8L16 22.1l-4.2-2.4v-4.8z" fill="currentColor" opacity="0.35"/>
          <path d="M5.6 12.5l4.2 2.4v4.8l-4.2 2.4-4.2-2.4v-4.8zM26.4 12.5l4.2 2.4v4.8l-4.2 2.4-4.2-2.4v-4.8zM10.8 21.5 15 23.9v4.8l-4.2 2.4-4.2-2.4v-4.8zM21.2 21.5l4.2 2.4v4.8l-4.2 2.4-4.2-2.4v-4.8z" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linejoin="round"/>
        </svg>
        <p class="empty-text">{{ $t('graph.waitingOntology') }}</p>
      </div>
    </div>

    <!-- Bottom legend (Bottom Left) -->
    <div v-if="graphData && entityTypes.length" class="graph-legend">
      <span class="legend-title">Entity Types</span>
      <div class="legend-items">
        <div class="legend-item" v-for="type in entityTypes" :key="type.name">
          <span class="legend-dot" :style="{ background: type.color }"></span>
          <span class="legend-label">{{ type.name }}</span>
        </div>
      </div>
    </div>
    
    <!-- Show edge labels toggle -->
    <div v-if="graphData" class="edge-labels-toggle">
      <label class="toggle-switch">
        <input type="checkbox" v-model="showEdgeLabels" />
        <span class="slider"></span>
      </label>
      <span class="toggle-label">Show Edge Labels</span>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch, nextTick, computed } from 'vue'
import * as d3 from 'd3'

const props = defineProps({
  graphData: Object,
  loading: Boolean,
  currentPhase: Number,
  isSimulating: Boolean
})

const emit = defineEmits(['refresh', 'toggle-maximize'])

const graphContainer = ref(null)
const graphSvg = ref(null)
const selectedItem = ref(null)
const showEdgeLabels = ref(true) // Edge labels are shown by default
const expandedSelfLoops = ref(new Set()) // Expanded self-loop items
const showSimulationFinishedHint = ref(false) // Hint shown after the simulation ends
const wasSimulating = ref(false) // Tracks whether a simulation was running before

// Dismiss the simulation-finished hint
const dismissFinishedHint = () => {
  showSimulationFinishedHint.value = false
}

// Watch isSimulating to detect when the simulation ends
// Only after a run was actually watched live: opening a finished run also flips
// isSimulating briefly (processing -> completed), and that needs no hint.
let simulatingSince = 0
watch(() => props.isSimulating, (newValue, oldValue) => {
  if (wasSimulating.value && !newValue && Date.now() - simulatingSince > 15000) {
    showSimulationFinishedHint.value = true
  }
  if (newValue && !wasSimulating.value) simulatingSince = Date.now()
  wasSimulating.value = newValue
}, { immediate: true })

// Toggle a self-loop item between expanded and collapsed
const toggleSelfLoop = (id) => {
  const newSet = new Set(expandedSelfLoops.value)
  if (newSet.has(id)) {
    newSet.delete(id)
  } else {
    newSet.add(id)
  }
  expandedSelfLoops.value = newSet
}

// Work out the entity types for the legend
const entityTypes = computed(() => {
  if (!props.graphData?.nodes) return []
  const typeMap = {}
  // A pleasant colour palette
  const colors = ['#FF6B35', '#004E89', '#7B2D8E', '#1A936F', '#C5283D', '#E9724C', '#3498db', '#9b59b6', '#27ae60', '#f39c12']
  
  props.graphData.nodes.forEach(node => {
    const type = node.labels?.find(l => l !== 'Entity') || 'Entity'
    if (!typeMap[type]) {
      typeMap[type] = { name: type, count: 0, color: colors[Object.keys(typeMap).length % colors.length] }
    }
    typeMap[type].count++
  })
  return Object.values(typeMap)
})

// Format a timestamp
const formatDateTime = (dateStr) => {
  if (!dateStr) return ''
  try {
    const date = new Date(dateStr)
    return date.toLocaleString('en-US', { 
      month: 'short', 
      day: 'numeric', 
      year: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
      hour12: true 
    })
  } catch {
    return dateStr
  }
}

const closeDetailPanel = () => {
  selectedItem.value = null
  expandedSelfLoops.value = new Set() // Reset the expanded state
}

let currentSimulation = null
let linkLabelsRef = null
let linkLabelBgRef = null

const renderGraph = () => {
  if (!graphSvg.value || !props.graphData) return
  
  // Stop the previous force simulation
  if (currentSimulation) {
    currentSimulation.stop()
  }
  
  const container = graphContainer.value
  const width = container.clientWidth
  const height = container.clientHeight
  
  const svg = d3.select(graphSvg.value)
    .attr('width', width)
    .attr('height', height)
    .attr('viewBox', `0 0 ${width} ${height}`)
    
  svg.selectAll('*').remove()
  
  const nodesData = props.graphData.nodes || []
  const edgesData = props.graphData.edges || []
  
  if (nodesData.length === 0) return

  // Prep data
  const nodeMap = {}
  nodesData.forEach(n => nodeMap[n.uuid] = n)
  
  const nodes = nodesData.map(n => ({
    id: n.uuid,
    name: n.name || 'Unnamed',
    type: n.labels?.find(l => l !== 'Entity') || 'Entity',
    rawData: n
  }))
  
  const nodeIds = new Set(nodes.map(n => n.id))
  
  // Process edge data: count the edges between each pair of nodes and index them
  const edgePairCount = {}
  const selfLoopEdges = {} // Self-loop edges grouped by node
  const tempEdges = edgesData
    .filter(e => nodeIds.has(e.source_node_uuid) && nodeIds.has(e.target_node_uuid))
  
  // Count the edges between each pair of nodes and collect self-loop edges
  tempEdges.forEach(e => {
    if (e.source_node_uuid === e.target_node_uuid) {
      // Self-loop: collect it into the array
      if (!selfLoopEdges[e.source_node_uuid]) {
        selfLoopEdges[e.source_node_uuid] = []
      }
      selfLoopEdges[e.source_node_uuid].push({
        ...e,
        source_name: nodeMap[e.source_node_uuid]?.name,
        target_name: nodeMap[e.target_node_uuid]?.name
      })
    } else {
      const pairKey = [e.source_node_uuid, e.target_node_uuid].sort().join('_')
      edgePairCount[pairKey] = (edgePairCount[pairKey] || 0) + 1
    }
  })
  
  // Track which edge of each node pair is currently being processed
  const edgePairIndex = {}
  const processedSelfLoopNodes = new Set() // Nodes whose self-loops have been processed
  
  const edges = []
  
  tempEdges.forEach(e => {
    const isSelfLoop = e.source_node_uuid === e.target_node_uuid
    
    if (isSelfLoop) {
      // Self-loop edge: add only one merged self-loop per node
      if (processedSelfLoopNodes.has(e.source_node_uuid)) {
        return // Already processed, skip
      }
      processedSelfLoopNodes.add(e.source_node_uuid)
      
      const allSelfLoops = selfLoopEdges[e.source_node_uuid]
      const nodeName = nodeMap[e.source_node_uuid]?.name || 'Unknown'
      
      edges.push({
        source: e.source_node_uuid,
        target: e.target_node_uuid,
        type: 'SELF_LOOP',
        name: `Self Relations (${allSelfLoops.length})`,
        curvature: 0,
        isSelfLoop: true,
        rawData: {
          isSelfLoopGroup: true,
          source_name: nodeName,
          target_name: nodeName,
          selfLoopCount: allSelfLoops.length,
          selfLoopEdges: allSelfLoops // Keep the details of every self-loop edge
        }
      })
      return
    }
    
    const pairKey = [e.source_node_uuid, e.target_node_uuid].sort().join('_')
    const totalCount = edgePairCount[pairKey]
    const currentIndex = edgePairIndex[pairKey] || 0
    edgePairIndex[pairKey] = currentIndex + 1
    
    // Check whether the edge runs in the normalised direction (source UUID < target UUID)
    const isReversed = e.source_node_uuid > e.target_node_uuid
    
    // Work out the curvature: spread multiple edges apart, draw a single edge straight
    let curvature = 0
    if (totalCount > 1) {
      // Spread the curvature evenly so the edges are clearly distinct
      // The curvature range grows with the edge count: more edges, wider range
      const curvatureRange = Math.min(1.2, 0.6 + totalCount * 0.15)
      curvature = ((currentIndex / (totalCount - 1)) - 0.5) * curvatureRange * 2
      
      // If the edge runs against the normalised direction, flip the curvature
      // so all edges are laid out in the same frame of reference and do not overlap because of direction
      if (isReversed) {
        curvature = -curvature
      }
    }
    
    edges.push({
      source: e.source_node_uuid,
      target: e.target_node_uuid,
      type: e.fact_type || e.name || 'RELATED',
      name: e.name || e.fact_type || 'RELATED',
      curvature,
      isSelfLoop: false,
      pairIndex: currentIndex,
      pairTotal: totalCount,
      rawData: {
        ...e,
        source_name: nodeMap[e.source_node_uuid]?.name,
        target_name: nodeMap[e.target_node_uuid]?.name
      }
    })
  })
    
  // Hivemind: size each node by how connected it is, so the hubs of the story stand out.
  const degree = {}
  const neighbourIds = {}
  edges.forEach(e => {
    if (e.isSelfLoop) return
    degree[e.source] = (degree[e.source] || 0) + 1
    degree[e.target] = (degree[e.target] || 0) + 1
    ;(neighbourIds[e.source] ||= new Set()).add(e.target)
    ;(neighbourIds[e.target] ||= new Set()).add(e.source)
  })
  const nodeRadius = (d) => 7 + Math.min(11, Math.sqrt(degree[d.id] || 0) * 2.4)
  const isNear = (a, b) => a === b || !!neighbourIds[a]?.has(b)
  const endId = (end) => (typeof end === 'object' ? end.id : end)

  // Color scale
  const colorMap = {}
  entityTypes.value.forEach(t => colorMap[t.name] = t.color)
  const getColor = (type) => colorMap[type] || '#999'

  // Simulation: adjust node spacing dynamically by edge count
  const simulation = d3.forceSimulation(nodes)
    .force('link', d3.forceLink(edges).id(d => d.id).distance(d => {
      // Adjust the distance dynamically by the number of edges between this pair of nodes
      // Base distance 150, plus 40 for each additional edge
      const baseDistance = 150
      const edgeCount = d.pairTotal || 1
      return baseDistance + (edgeCount - 1) * 50
    }))
    .force('charge', d3.forceManyBody().strength(-400))
    .force('center', d3.forceCenter(width / 2, height / 2))
    .force('collide', d3.forceCollide(50))
    // Add a pull towards the centre so separate node clusters gather in the middle
    .force('x', d3.forceX(width / 2).strength(0.04))
    .force('y', d3.forceY(height / 2).strength(0.04))
  
  currentSimulation = simulation

  const g = svg.append('g')
  
  // Zoom
  svg.call(d3.zoom().extent([[0, 0], [width, height]]).scaleExtent([0.1, 4]).on('zoom', (event) => {
    g.attr('transform', event.transform)
  }))

  // Links: use path elements so edges can curve
  const linkGroup = g.append('g').attr('class', 'links')
  
  // Compute the curved path
  const getLinkPath = (d) => {
    const sx = d.source.x, sy = d.source.y
    const tx = d.target.x, ty = d.target.y
    
    // Detect a self-loop
    if (d.isSelfLoop) {
      // Self-loop: draw an arc that leaves the node and comes back
      const loopRadius = 30
      // Leave from the right of the node and loop back round
      const x1 = sx + 8  // Start offset
      const y1 = sy - 4
      const x2 = sx + 8  // End offset
      const y2 = sy + 4
      // Draw the self-loop as an arc (sweep-flag=1 is clockwise)
      return `M${x1},${y1} A${loopRadius},${loopRadius} 0 1,1 ${x2},${y2}`
    }
    
    if (d.curvature === 0) {
      // Straight line
      return `M${sx},${sy} L${tx},${ty}`
    }
    
    // Compute the curve control point, adjusted dynamically by edge count and distance
    const dx = tx - sx, dy = ty - sy
    const dist = Math.sqrt(dx * dx + dy * dy)
    // Offset perpendicular to the line, proportional to the distance, so the curve is clearly visible
    // The more edges, the larger the offset as a share of the distance
    const pairTotal = d.pairTotal || 1
    const offsetRatio = 0.25 + pairTotal * 0.05 // 25% base, plus 5% for each additional edge
    const baseOffset = Math.max(35, dist * offsetRatio)
    const offsetX = -dy / dist * d.curvature * baseOffset
    const offsetY = dx / dist * d.curvature * baseOffset
    const cx = (sx + tx) / 2 + offsetX
    const cy = (sy + ty) / 2 + offsetY
    
    return `M${sx},${sy} Q${cx},${cy} ${tx},${ty}`
  }
  
  // Compute the curve midpoint (used to position the label)
  const getLinkMidpoint = (d) => {
    const sx = d.source.x, sy = d.source.y
    const tx = d.target.x, ty = d.target.y
    
    // Detect a self-loop
    if (d.isSelfLoop) {
      // Self-loop label position: to the right of the node
      return { x: sx + 70, y: sy }
    }
    
    if (d.curvature === 0) {
      return { x: (sx + tx) / 2, y: (sy + ty) / 2 }
    }
    
    // Midpoint of the quadratic Bezier curve, t=0.5
    const dx = tx - sx, dy = ty - sy
    const dist = Math.sqrt(dx * dx + dy * dy)
    const pairTotal = d.pairTotal || 1
    const offsetRatio = 0.25 + pairTotal * 0.05
    const baseOffset = Math.max(35, dist * offsetRatio)
    const offsetX = -dy / dist * d.curvature * baseOffset
    const offsetY = dx / dist * d.curvature * baseOffset
    const cx = (sx + tx) / 2 + offsetX
    const cy = (sy + ty) / 2 + offsetY
    
    // Quadratic Bezier formula B(t) = (1-t)²P0 + 2(1-t)tP1 + t²P2, t=0.5
    const midX = 0.25 * sx + 0.5 * cx + 0.25 * tx
    const midY = 0.25 * sy + 0.5 * cy + 0.25 * ty
    
    return { x: midX, y: midY }
  }
  
  const link = linkGroup.selectAll('path')
    .data(edges)
    .enter().append('path')
    .attr('stroke', '#C0C0C0')
    .attr('stroke-width', 1.5)
    .attr('fill', 'none')
    .style('cursor', 'pointer')
    .on('click', (event, d) => {
      event.stopPropagation()
      // Reset the style of the previously selected edge
      linkGroup.selectAll('path').attr('stroke', '#C0C0C0').attr('stroke-width', 1.5)
      linkLabelBg.attr('fill', 'rgba(255,255,255,0.95)')
      linkLabels.attr('fill', '#666')
      // Highlight the selected edge
      d3.select(event.target).attr('stroke', '#3498db').attr('stroke-width', 3)
      
      selectedItem.value = {
        type: 'edge',
        data: d.rawData
      }
    })

  // Link labels background (a white background makes the text easier to read)
  const linkLabelBg = linkGroup.selectAll('rect')
    .data(edges)
    .enter().append('rect')
    .attr('fill', 'rgba(255,255,255,0.95)')
    .attr('rx', 3)
    .attr('ry', 3)
    .style('cursor', 'pointer')
    .style('pointer-events', 'all')
    .style('display', showEdgeLabels.value ? 'block' : 'none')
    .on('click', (event, d) => {
      event.stopPropagation()
      linkGroup.selectAll('path').attr('stroke', '#C0C0C0').attr('stroke-width', 1.5)
      linkLabelBg.attr('fill', 'rgba(255,255,255,0.95)')
      linkLabels.attr('fill', '#666')
      // Highlight the matching edge
      link.filter(l => l === d).attr('stroke', '#3498db').attr('stroke-width', 3)
      d3.select(event.target).attr('fill', 'rgba(52, 152, 219, 0.1)')
      
      selectedItem.value = {
        type: 'edge',
        data: d.rawData
      }
    })

  // Link labels
  const linkLabels = linkGroup.selectAll('text')
    .data(edges)
    .enter().append('text')
    .text(d => d.name)
    .attr('font-size', '9px')
    .attr('fill', '#666')
    .attr('text-anchor', 'middle')
    .attr('dominant-baseline', 'middle')
    .style('cursor', 'pointer')
    .style('pointer-events', 'all')
    .style('font-family', 'system-ui, sans-serif')
    .style('display', showEdgeLabels.value ? 'block' : 'none')
    .on('click', (event, d) => {
      event.stopPropagation()
      linkGroup.selectAll('path').attr('stroke', '#C0C0C0').attr('stroke-width', 1.5)
      linkLabelBg.attr('fill', 'rgba(255,255,255,0.95)')
      linkLabels.attr('fill', '#666')
      // Highlight the matching edge
      link.filter(l => l === d).attr('stroke', '#3498db').attr('stroke-width', 3)
      d3.select(event.target).attr('fill', '#3498db')
      
      selectedItem.value = {
        type: 'edge',
        data: d.rawData
      }
    })
  
  // Keep references so visibility can be toggled from outside
  linkLabelsRef = linkLabels
  linkLabelBgRef = linkLabelBg

  // Nodes group
  const nodeGroup = g.append('g').attr('class', 'nodes')
  
  // Node circles
  const node = nodeGroup.selectAll('circle')
    .data(nodes)
    .enter().append('circle')
    .attr('r', nodeRadius)
    .attr('fill', d => getColor(d.type))
    .attr('stroke', '#fff')
    .attr('stroke-width', 2.5)
    .style('cursor', 'pointer')
    .call(d3.drag()
      .on('start', (event, d) => {
        // Only record the position, do not restart the simulation (tells a click from a drag)
        d.fx = d.x
        d.fy = d.y
        d._dragStartX = event.x
        d._dragStartY = event.y
        d._isDragging = false
      })
      .on('drag', (event, d) => {
        // Detect whether a real drag has started (moved past the threshold)
        const dx = event.x - d._dragStartX
        const dy = event.y - d._dragStartY
        const distance = Math.sqrt(dx * dx + dy * dy)
        
        if (!d._isDragging && distance > 3) {
          // Restart the simulation only once a real drag is first detected
          d._isDragging = true
          simulation.alphaTarget(0.3).restart()
        }
        
        if (d._isDragging) {
          d.fx = event.x
          d.fy = event.y
        }
      })
      .on('end', (event, d) => {
        // Let the simulation cool down only if there was a real drag
        if (d._isDragging) {
          simulation.alphaTarget(0)
        }
        d.fx = null
        d.fy = null
        d._isDragging = false
      })
    )
    .on('click', (event, d) => {
      event.stopPropagation()
      // Reset every node style
      node.attr('stroke', '#fff').attr('stroke-width', 2.5)
      linkGroup.selectAll('path').attr('stroke', '#C0C0C0').attr('stroke-width', 1.5)
      // Highlight the selected node
      d3.select(event.target).attr('stroke', '#E91E63').attr('stroke-width', 4)
      // Highlight the edges connected to this node
      link.filter(l => l.source.id === d.id || l.target.id === d.id)
        .attr('stroke', '#E91E63')
        .attr('stroke-width', 2.5)
      
      selectedItem.value = {
        type: 'node',
        data: d.rawData,
        entityType: d.type,
        color: getColor(d.type)
      }
    })
    .on('mouseenter', (event, d) => {
      if (!selectedItem.value || selectedItem.value.data?.uuid !== d.rawData.uuid) {
        d3.select(event.target).attr('stroke', '#333').attr('stroke-width', 3)
      }
      // Hivemind: fade everything that is not this node or one step away from it.
      if (d._isDragging) return
      const near = (l) => endId(l.source) === d.id || endId(l.target) === d.id
      node.style('opacity', n => (isNear(d.id, n.id) ? 1 : 0.12))
      nodeLabels.style('opacity', n => (isNear(d.id, n.id) ? 1 : 0.1))
      link.style('opacity', l => (near(l) ? 1 : 0.06))
      linkLabels.style('opacity', l => (near(l) ? 1 : 0.04))
      linkLabelBg.style('opacity', l => (near(l) ? 1 : 0.04))
    })
    .on('mouseleave', (event, d) => {
      if (!selectedItem.value || selectedItem.value.data?.uuid !== d.rawData.uuid) {
        d3.select(event.target).attr('stroke', '#fff').attr('stroke-width', 2.5)
      }
      node.style('opacity', 1)
      nodeLabels.style('opacity', 1)
      link.style('opacity', 1)
      linkLabels.style('opacity', 1)
      linkLabelBg.style('opacity', 1)
    })

  // Node Labels
  const nodeLabels = nodeGroup.selectAll('text')
    .data(nodes)
    .enter().append('text')
    .text(d => d.name.length > 20 ? d.name.substring(0, 19) + '…' : d.name)
    .attr('font-size', d => ((degree[d.id] || 0) >= 6 ? '12px' : '11px'))
    .attr('fill', '#333')
    .attr('font-weight', d => ((degree[d.id] || 0) >= 6 ? '600' : '500'))
    .attr('dx', d => nodeRadius(d) + 4)
    .attr('paint-order', 'stroke')
    .attr('stroke', 'rgba(255,255,255,0.85)')
    .attr('stroke-width', 3)
    .attr('stroke-linejoin', 'round')
    .attr('dy', 4)
    .style('pointer-events', 'none')
    .style('font-family', 'system-ui, sans-serif')

  simulation.on('tick', () => {
    // Update the curved paths
    link.attr('d', d => getLinkPath(d))
    
    // Update edge label positions (no rotation: horizontal text is easier to read)
    linkLabels.each(function(d) {
      const mid = getLinkMidpoint(d)
      d3.select(this)
        .attr('x', mid.x)
        .attr('y', mid.y)
        .attr('transform', '') // Remove rotation, keep it horizontal
    })
    
    // Update the edge label backgrounds
    linkLabelBg.each(function(d, i) {
      const mid = getLinkMidpoint(d)
      const textEl = linkLabels.nodes()[i]
      const bbox = textEl.getBBox()
      d3.select(this)
        .attr('x', mid.x - bbox.width / 2 - 4)
        .attr('y', mid.y - bbox.height / 2 - 2)
        .attr('width', bbox.width + 8)
        .attr('height', bbox.height + 4)
        .attr('transform', '') // Remove rotation
    })

    node
      .attr('cx', d => d.x)
      .attr('cy', d => d.y)

    nodeLabels
      .attr('x', d => d.x)
      .attr('y', d => d.y)
  })
  
  // Clicking empty space closes the detail panel
  svg.on('click', () => {
    selectedItem.value = null
    node.attr('stroke', '#fff').attr('stroke-width', 2.5)
    linkGroup.selectAll('path').attr('stroke', '#C0C0C0').attr('stroke-width', 1.5)
    linkLabelBg.attr('fill', 'rgba(255,255,255,0.95)')
    linkLabels.attr('fill', '#666')
  })
}

watch(() => props.graphData, () => {
  nextTick(renderGraph)
}, { deep: true })

// Watch the show-edge-labels toggle
watch(showEdgeLabels, (newVal) => {
  if (linkLabelsRef) {
    linkLabelsRef.style('display', newVal ? 'block' : 'none')
  }
  if (linkLabelBgRef) {
    linkLabelBgRef.style('display', newVal ? 'block' : 'none')
  }
})

const handleResize = () => {
  nextTick(renderGraph)
}

onMounted(() => {
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  if (currentSimulation) {
    currentSimulation.stop()
  }
})
</script>

<style scoped>
.graph-panel {
  position: relative;
  width: 100%;
  height: 100%;
  overflow: hidden;
  background-color: var(--hm-paper);
  background-image: radial-gradient(var(--hm-line-strong) 1px, transparent 1px);
  background-size: 20px 20px;
}

/* Toolbar */
.panel-header {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  z-index: 10;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--hm-space-4) var(--hm-space-5);
  background: linear-gradient(to bottom, rgba(243, 240, 232, 0.96) 40%, rgba(243, 240, 232, 0));
  pointer-events: none;
}

.panel-title {
  font-size: var(--hm-text-2xs);
  font-weight: 500;
  font-family: var(--hm-font-mono);
  letter-spacing: var(--hm-tracking-label);
  text-transform: uppercase;
  color: var(--hm-ink-3);
  pointer-events: auto;
}

.header-tools {
  display: flex;
  align-items: center;
  gap: var(--hm-space-2);
  pointer-events: auto;
}

.tool-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  height: 30px;
  padding: 0 var(--hm-space-3);
  background: var(--hm-surface);
  border: 1px solid var(--hm-line-strong);
  border-radius: var(--hm-radius-sm);
  color: var(--hm-ink-2);
  font-size: var(--hm-text-xs);
  font-weight: 600;
  cursor: pointer;
  transition: background-color var(--hm-duration-fast) var(--hm-ease), border-color var(--hm-duration-fast) var(--hm-ease), color var(--hm-duration-fast) var(--hm-ease);
}

.tool-btn.icon-only {
  width: 30px;
  padding: 0;
}

.tool-btn:hover:not(:disabled) {
  background: var(--hm-surface-2);
  border-color: var(--hm-ink-5);
  color: var(--hm-ink);
}

.tool-btn:disabled {
  color: var(--hm-ink-5);
  cursor: not-allowed;
}

.tool-btn .btn-text {
  font-size: var(--hm-text-xs);
}

.icon-refresh.spinning {
  animation: spin 0.8s linear infinite;
}

@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }

.graph-container {
  width: 100%;
  height: 100%;
}

.graph-view,
.graph-svg {
  display: block;
  width: 100%;
  height: 100%;
}

/* Loading and empty states */
.graph-state {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--hm-space-3);
  text-align: center;
  font-size: var(--hm-text-sm);
  color: var(--hm-ink-4);
}

.empty-icon {
  color: var(--hm-ink-5);
}

.empty-text {
  max-width: 260px;
}

.loading-spinner {
  width: 28px;
  height: 28px;
  border: 2px solid var(--hm-line-strong);
  border-top-color: var(--hm-ink);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

/* Entity type legend */
.graph-legend {
  position: absolute;
  bottom: var(--hm-space-5);
  left: var(--hm-space-5);
  z-index: 10;
  padding: var(--hm-space-3) var(--hm-space-4);
  background: rgba(255, 255, 255, 0.96);
  border: 1px solid var(--hm-line);
  border-radius: var(--hm-radius-md);
  box-shadow: var(--hm-shadow-sm);
  backdrop-filter: blur(4px);
}

.legend-title {
  display: block;
  margin-bottom: var(--hm-space-2);
  font-size: var(--hm-text-2xs);
  font-weight: 500;
  font-family: var(--hm-font-mono);
  letter-spacing: var(--hm-tracking-label);
  text-transform: uppercase;
  color: var(--hm-ink-4);
}

.legend-items {
  display: flex;
  flex-wrap: wrap;
  gap: 6px var(--hm-space-4);
  max-width: 340px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: var(--hm-text-xs);
  color: var(--hm-ink-2);
}

.legend-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.legend-label {
  white-space: nowrap;
}

/* Edge label toggle */
.edge-labels-toggle {
  position: absolute;
  top: 60px;
  right: var(--hm-space-5);
  z-index: 10;
  display: flex;
  align-items: center;
  gap: var(--hm-space-2);
  height: 34px;
  padding: 0 var(--hm-space-3) 0 var(--hm-space-2);
  background: var(--hm-surface);
  border: 1px solid var(--hm-line-strong);
  border-radius: var(--hm-radius-pill);
  box-shadow: var(--hm-shadow-xs);
}

.toggle-switch {
  position: relative;
  display: inline-block;
  width: 32px;
  height: 18px;
}

.toggle-switch input {
  position: absolute;
  opacity: 0;
  width: 0;
  height: 0;
}

.slider {
  position: absolute;
  inset: 0;
  background-color: var(--hm-line-strong);
  border-radius: var(--hm-radius-pill);
  cursor: pointer;
  transition: background-color var(--hm-duration) var(--hm-ease);
}

.slider:before {
  content: "";
  position: absolute;
  left: 2px;
  bottom: 2px;
  width: 14px;
  height: 14px;
  background-color: var(--hm-surface);
  border-radius: 50%;
  box-shadow: var(--hm-shadow-xs);
  transition: transform var(--hm-duration) var(--hm-ease);
}

input:checked + .slider {
  background-color: var(--hm-ink);
}

input:checked + .slider:before {
  transform: translateX(14px);
}

input:focus-visible + .slider {
  outline: 2px solid var(--hm-ink);
  outline-offset: 2px;
}

.toggle-label {
  font-size: var(--hm-text-xs);
  font-weight: 500;
  color: var(--hm-ink-2);
}

/* Node / edge detail panel */
.detail-panel {
  position: absolute;
  top: 60px;
  right: var(--hm-space-5);
  z-index: 20;
  display: flex;
  flex-direction: column;
  width: 340px;
  max-height: calc(100% - 100px);
  overflow: hidden;
  background: var(--hm-surface);
  border: 1px solid var(--hm-line);
  border-radius: var(--hm-radius-lg);
  box-shadow: var(--hm-shadow-lg);
  font-family: var(--hm-font-sans);
  font-size: var(--hm-text-sm);
}

.detail-panel-header {
  display: flex;
  align-items: center;
  gap: var(--hm-space-2);
  flex-shrink: 0;
  padding: var(--hm-space-2) var(--hm-space-2) var(--hm-space-2) var(--hm-space-4);
  border-bottom: 1px solid var(--hm-line);
}

.detail-title {
  font-family: var(--hm-font-display);
  font-size: var(--hm-text-base);
  font-weight: 500;
  color: var(--hm-ink);
}

.detail-type-badge {
  display: inline-flex;
  align-items: center;
  height: 20px;
  margin-left: auto;
  padding: 0 var(--hm-space-2);
  border-radius: var(--hm-radius-pill);
  font-size: var(--hm-text-2xs);
  font-weight: 600;
  white-space: nowrap;
}

.detail-close {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  flex-shrink: 0;
  margin-left: auto;
  border: none;
  border-radius: var(--hm-radius-sm);
  background: transparent;
  color: var(--hm-ink-4);
  cursor: pointer;
  transition: background-color var(--hm-duration-fast) var(--hm-ease), color var(--hm-duration-fast) var(--hm-ease);
}

.detail-type-badge + .detail-close {
  margin-left: 0;
}

.detail-close:hover {
  background: var(--hm-surface-3);
  color: var(--hm-ink);
}

.detail-content {
  flex: 1;
  overflow-y: auto;
  padding: var(--hm-space-4);
}

.detail-row {
  display: flex;
  flex-wrap: wrap;
  gap: var(--hm-space-1) var(--hm-space-2);
  margin-bottom: var(--hm-space-3);
}

.detail-label {
  min-width: 80px;
  font-size: var(--hm-text-xs);
  font-weight: 500;
  color: var(--hm-ink-4);
}

.detail-value {
  flex: 1;
  color: var(--hm-ink-2);
  word-break: break-word;
}

.detail-value.uuid-text {
  font-family: var(--hm-font-mono);
  font-size: var(--hm-text-2xs);
  color: var(--hm-ink-3);
}

.detail-value.fact-text {
  line-height: var(--hm-leading-normal);
  color: var(--hm-ink-2);
}

.detail-section {
  margin-top: var(--hm-space-4);
  padding-top: var(--hm-space-4);
  border-top: 1px solid var(--hm-line);
}

.section-title {
  margin-bottom: var(--hm-space-2);
  font-size: var(--hm-text-2xs);
  font-weight: 500;
  font-family: var(--hm-font-mono);
  letter-spacing: var(--hm-tracking-label);
  text-transform: uppercase;
  color: var(--hm-ink-4);
}

.properties-list {
  display: flex;
  flex-direction: column;
  gap: var(--hm-space-2);
}

.property-item {
  display: flex;
  gap: var(--hm-space-2);
}

.property-key {
  min-width: 90px;
  font-family: var(--hm-font-mono);
  font-size: var(--hm-text-xs);
  color: var(--hm-ink-4);
}

.property-value {
  flex: 1;
  color: var(--hm-ink-2);
}

.summary-text {
  font-size: var(--hm-text-sm);
  line-height: var(--hm-leading-relaxed);
  color: var(--hm-ink-2);
}

.labels-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.label-tag {
  display: inline-block;
  padding: 3px var(--hm-space-2);
  background: var(--hm-surface-2);
  border: 1px solid var(--hm-line);
  border-radius: var(--hm-radius-xs);
  font-size: var(--hm-text-xs);
  color: var(--hm-ink-2);
}

.episodes-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.episode-tag {
  display: inline-block;
  padding: 6px var(--hm-space-2);
  background: var(--hm-surface-2);
  border: 1px solid var(--hm-line);
  border-radius: var(--hm-radius-xs);
  font-family: var(--hm-font-mono);
  font-size: var(--hm-text-2xs);
  color: var(--hm-ink-3);
  word-break: break-all;
}

.edge-relation-header {
  margin-bottom: var(--hm-space-4);
  padding: var(--hm-space-3);
  background: var(--hm-surface-2);
  border: 1px solid var(--hm-line);
  border-radius: var(--hm-radius-md);
  font-size: var(--hm-text-sm);
  font-weight: 600;
  line-height: var(--hm-leading-normal);
  color: var(--hm-ink);
  word-break: break-word;
}

/* Live / finished hints: ink toasts over the canvas */
.graph-building-hint {
  position: absolute;
  bottom: 160px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 100;
  display: flex;
  align-items: center;
  gap: var(--hm-space-2);
  max-width: calc(100% - 48px);
  padding: var(--hm-space-2) var(--hm-space-4);
  background: var(--hm-ink);
  color: var(--hm-surface);
  border-radius: var(--hm-radius-md);
  box-shadow: var(--hm-shadow-md);
  font-size: var(--hm-text-sm);
  font-weight: 500;
}

.memory-icon-wrapper {
  display: flex;
  align-items: center;
  justify-content: center;
  animation: breathe 2s ease-in-out infinite;
}

.memory-icon {
  width: 16px;
  height: 16px;
  color: var(--hm-signal);
}

@keyframes breathe {
  0%, 100% { opacity: 0.6; }
  50% { opacity: 1; }
}

.finished-hint .hint-icon-wrapper {
  display: flex;
  align-items: center;
  justify-content: center;
}

.finished-hint .hint-icon {
  width: 16px;
  height: 16px;
  color: var(--hm-signal);
}

.finished-hint .hint-text {
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.hint-close-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  width: 24px;
  height: 24px;
  margin-left: var(--hm-space-1);
  border: none;
  border-radius: var(--hm-radius-xs);
  background: transparent;
  color: rgba(255, 255, 255, 0.7);
  cursor: pointer;
  transition: background-color var(--hm-duration-fast) var(--hm-ease), color var(--hm-duration-fast) var(--hm-ease);
}

.hint-close-btn:hover {
  background: rgba(255, 255, 255, 0.12);
  color: var(--hm-surface);
}

/* Self-loop groups */
.self-loop-header {
  display: flex;
  align-items: center;
  gap: var(--hm-space-2);
}

.self-loop-count {
  margin-left: auto;
  padding: 2px var(--hm-space-2);
  background: var(--hm-surface);
  border: 1px solid var(--hm-line);
  border-radius: var(--hm-radius-pill);
  font-size: var(--hm-text-2xs);
  font-weight: 500;
  color: var(--hm-ink-3);
  white-space: nowrap;
}

.self-loop-list {
  display: flex;
  flex-direction: column;
  gap: var(--hm-space-2);
}

.self-loop-item {
  overflow: hidden;
  background: var(--hm-surface);
  border: 1px solid var(--hm-line);
  border-radius: var(--hm-radius-md);
}

.self-loop-item-header {
  display: flex;
  align-items: center;
  gap: var(--hm-space-2);
  padding: var(--hm-space-2) var(--hm-space-3);
  cursor: pointer;
  transition: background-color var(--hm-duration-fast) var(--hm-ease);
}

.self-loop-item-header:hover,
.self-loop-item.expanded .self-loop-item-header {
  background: var(--hm-surface-2);
}

.self-loop-index {
  font-family: var(--hm-font-mono);
  font-size: var(--hm-text-2xs);
  color: var(--hm-ink-4);
}

.self-loop-name {
  flex: 1;
  font-size: var(--hm-text-xs);
  font-weight: 600;
  color: var(--hm-ink-2);
}

.self-loop-toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border-radius: var(--hm-radius-xs);
  background: var(--hm-surface-3);
  font-size: var(--hm-text-sm);
  font-weight: 600;
  color: var(--hm-ink-3);
}

.self-loop-item-content {
  padding: var(--hm-space-3);
  border-top: 1px solid var(--hm-line);
}

.self-loop-item-content .detail-row {
  margin-bottom: var(--hm-space-2);
}

.self-loop-item-content .detail-label {
  min-width: 60px;
  font-size: var(--hm-text-2xs);
}

.self-loop-item-content .detail-value {
  font-size: var(--hm-text-xs);
}

.self-loop-episodes {
  margin-top: var(--hm-space-2);
}

.episodes-list.compact {
  flex-direction: row;
  flex-wrap: wrap;
  gap: var(--hm-space-1);
}

.episode-tag.small {
  padding: 2px 6px;
  font-size: 10px;
}
</style>
