<template>
  <section class="card health-card" :class="`health--${health?.overall || 'amber'}`">
    <header class="card-head">
      <div>
        <h3>{{ $t('analytics.healthTitle') }}</h3>
        <p class="sub">{{ $t('analytics.healthSubtitle') }}</p>
      </div>
      <span class="badge" :class="health?.overall">{{ (health?.overall || '–').toUpperCase() }}</span>
    </header>
    <p class="headline">{{ health?.headline }}</p>
    <ul v-if="health?.reasons?.length" class="reasons">
      <li v-for="(r, i) in health.reasons" :key="i">{{ r }}</li>
    </ul>
    <div class="checks">
      <div v-for="c in health?.checks || []" :key="c.id" class="check" :class="c.level">
        <span class="dot" />
        <div class="check-body">
          <div class="check-label">{{ c.label }}</div>
          <div class="check-detail">{{ c.detail }}</div>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
defineProps({
  health: { type: Object, default: null }
})
</script>

<style scoped>
.health-card { border-left: 4px solid var(--hm-ink-5); }
.health--green { border-left-color: #1baf7a; }
.health--amber { border-left-color: #eda100; }
.health--red { border-left-color: #eb6834; }
.badge {
  font-family: var(--hm-font-mono); font-size: 11px; letter-spacing: 0.08em;
  padding: 4px 10px; border-radius: 999px; background: var(--hm-surface-3); color: var(--hm-ink);
}
.badge.green { background: rgba(27, 175, 122, 0.15); color: #0f7a52; }
.badge.amber { background: rgba(237, 161, 0, 0.18); color: #8a5a00; }
.badge.red { background: rgba(235, 104, 52, 0.16); color: #a33a12; }
.headline { margin: 0 0 10px; font-size: var(--hm-text-sm); color: var(--hm-ink); }
.reasons { margin: 0 0 14px; padding-left: 18px; color: var(--hm-ink-3); font-size: 13px; }
.reasons li { margin-bottom: 4px; }
.checks { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 10px; }
.check {
  display: flex; gap: 10px; align-items: flex-start;
  padding: 10px 12px; border: 1px solid var(--hm-line); border-radius: var(--hm-radius-md);
  background: var(--hm-surface-2);
}
.dot { width: 10px; height: 10px; border-radius: 50%; margin-top: 4px; flex-shrink: 0; background: var(--hm-ink-5); }
.check.green .dot { background: #1baf7a; }
.check.amber .dot { background: #eda100; }
.check.red .dot { background: #eb6834; }
.check-label { font-size: 12px; font-weight: 600; color: var(--hm-ink); }
.check-detail { font-size: 12px; color: var(--hm-ink-3); margin-top: 2px; line-height: 1.4; }
</style>
