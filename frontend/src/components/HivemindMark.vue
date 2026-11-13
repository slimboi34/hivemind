<template>
  <svg
    class="hm-mark"
    :class="[`hm-mark--${tone}`, { 'hm-mark--animated': animated }]"
    viewBox="0 0 32 32"
    :width="size"
    :height="size"
    fill="none"
    role="img"
    aria-label="Hivemind"
  >
    <!-- Geometry copied from brand/mark.svg. Six agents draw the cell. -->
    <path
      class="hm-mark__agents"
      d="M 28.500,16.000 L 22.250,26.825 L 9.750,26.825 L 3.500,16.000 L 9.750,5.175 L 22.250,5.175 L 28.500,16.000"
      fill="none"
      stroke-width="2.25"
      stroke-linecap="round"
      stroke-dasharray="7.9 4.6"
      stroke-dashoffset="10.2"
      pathLength="75"
    />
    <!-- The amber hex is the mind that appears between them. -->
    <path
      class="hm-mark__mind"
      d="M 16.000,10.000 L 21.196,13.000 L 21.196,19.000 L 16.000,22.000 L 10.804,19.000 L 10.804,13.000 Z"
    />
  </svg>
</template>

<script setup>
defineProps({
  size: { type: [Number, String], default: 32 },
  tone: { type: String, default: 'light' }, // 'light' (mark.svg) | 'dark' (mark-on-dark.svg) | 'mono' (mark-mono.svg)
  animated: { type: Boolean, default: false }
})
</script>

<style scoped>
.hm-mark {
  display: block;
  flex-shrink: 0;
  overflow: visible;
}

.hm-mark--light .hm-mark__agents { stroke: #16140F; }
.hm-mark--light .hm-mark__mind { fill: #D4890A; }
.hm-mark--dark .hm-mark__agents { stroke: #F3F0E8; }
.hm-mark--dark .hm-mark__mind { fill: #F0A818; }
.hm-mark--mono .hm-mark__agents { stroke: #16140F; }
.hm-mark--mono .hm-mark__mind { fill: #16140F; }

/* The six dashes travel one slot (12.5 of 75) per cycle, so the loop is seamless. */
.hm-mark--animated .hm-mark__agents {
  animation: hm-mark-orbit 3.2s linear infinite;
}

.hm-mark--animated .hm-mark__mind {
  transform-origin: 16px 16px;
  animation: hm-mark-appear 1.1s var(--hm-ease) 0.2s both;
}

@keyframes hm-mark-orbit {
  from { stroke-dashoffset: 10.2; }
  to { stroke-dashoffset: -2.3; }
}

@keyframes hm-mark-appear {
  from { opacity: 0; transform: scale(0.6); }
  to { opacity: 1; transform: scale(1); }
}
</style>
