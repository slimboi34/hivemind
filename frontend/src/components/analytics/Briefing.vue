<template>
  <section class="card briefing" aria-labelledby="briefing-title">
    <header class="card-head">
      <div>
        <h3 id="briefing-title">{{ $t('analytics.briefTitle') }}</h3>
        <p class="sub">{{ $t('analytics.briefSubtitle') }}</p>
      </div>
      <div class="head-actions">
        <span class="source" :class="sourceClass"><span class="source-dot"></span>{{ sourceText }}</span>
        <button v-if="finished && briefing?.can_write && !isPublic" class="ghost-btn" :disabled="writing" @click="emit('write', true)">
          {{ $t('analytics.recapRewrite') }}
        </button>
        <button class="hm-btn hm-btn--primary hm-btn--sm" :disabled="downloading || !hasWriting" @click="emit('download')">
          {{ downloading ? $t('analytics.briefPreparingPdf') : $t('analytics.briefDownloadPdf') }}
        </button>
      </div>
    </header>

    <p v-if="writeError" class="write-error">{{ $t('analytics.briefWriteFailed', { error: writeError }) }}</p>
    <p v-if="!hasWriting" class="empty">{{ $t('analytics.briefEmpty') }}</p>

    <template v-else>
      <p class="eyebrow">{{ $t('analytics.briefBottomLine') }}</p>
      <p class="bottom-line" :class="{ fading: writing }">{{ reading.bottom_line }}</p>

      <p class="confidence">
        <span class="tag" :class="`conf-${confidence.level}`">{{ $t('analytics.briefTrust') }}: {{ $t(`analytics.briefConfidence.${confidence.level}`) }}</span>
        <span>{{ confidence.why }}</span>
      </p>
      <p v-if="facts.run?.cast?.note" class="cast-note">{{ facts.run.cast.note }}</p>

      <ul v-if="reading.what_it_means?.length" class="means" :class="{ fading: writing }">
        <li v-for="(m, i) in reading.what_it_means" :key="i">{{ m }}</li>
      </ul>

      <div class="two">
        <div class="panel">
          <h4>{{ $t('analytics.briefAgree') }}</h4>
          <p v-if="!reading.consensus?.length" class="none">{{ $t('analytics.briefNoAgree') }}</p>
          <div v-for="(c, i) in reading.consensus" :key="i" class="point">
            <span class="tag" :class="`str-${c.strength}`">{{ $t(`analytics.briefStrength.${c.strength}`) }}</span>
            <p>{{ c.point }}</p>
            <p v-if="c.held_by?.length" class="held">{{ $t('analytics.briefHeldBy') }} {{ c.held_by.join(', ') }}</p>
          </div>
        </div>
        <div class="panel">
          <h4>{{ $t('analytics.briefSplit') }}</h4>
          <p v-if="!reading.splits?.length" class="none">{{ $t('analytics.briefNoSplit') }}</p>
          <div v-for="(s, i) in reading.splits" :key="i" class="point">
            <p class="issue">{{ s.issue }}</p>
            <p><strong>{{ $t('analytics.briefSideA') }}</strong> {{ s.side_a }}</p>
            <p><strong>{{ $t('analytics.briefSideB') }}</strong> {{ s.side_b }}</p>
          </div>
        </div>
      </div>

      <h4 class="block-title">{{ $t('analytics.briefGroups') }}</h4>
      <p class="block-sub">{{ $t('analytics.briefGroupsSub') }}</p>
      <div class="groups">
        <article v-for="g in groups" :key="g.key" class="group" :class="{ quiet: g.reading.stance === 'quiet' }">
          <header>
            <h5>{{ g.label }}</h5>
            <span class="tag" :class="`stance-${g.reading.stance}`">{{ $t(`analytics.briefStance.${g.reading.stance}`) }}</span>
          </header>
          <p class="meta">
            {{ $t('analytics.briefTookPart', { active: g.active, total: g.members }) }} ·
            {{ $t('analytics.recapStatPosts', { n: fmt(g.posts) }) }} ·
            {{ $t('analytics.recapStatReplies', { n: fmt(g.replies) }) }}
          </p>
          <p v-if="g.reception !== null" class="reception" :title="$t('analytics.briefReceptionHint')">
            <span class="rec-bar"><span :style="{ width: pct(g.reception) }"></span></span>
            {{ $t('analytics.briefReception', { pct: pct(g.reception), n: g.approving_received + g.disapproving_received }) }}
          </p>
          <p class="reaction" :class="{ fading: writing }">{{ g.reading.reaction }}</p>
          <p v-if="g.reading.likely_next" class="next" :class="{ fading: writing }">
            <strong>{{ $t('analytics.briefLikelyNext') }}</strong> {{ g.reading.likely_next }}
          </p>
          <blockquote v-if="g.said?.length" class="quote">
            <p :class="{ open: openQuote === g.key }" @click="openQuote = openQuote === g.key ? null : g.key">{{ g.said[0].text }}</p>
            <footer>
              <button class="author" @click="emit('update:selected', g.said[0].author)">{{ g.said[0].author }}</button>
              <span>· {{ $t(`analytics.platforms.${g.said[0].platform}`) }}</span>
            </footer>
          </blockquote>
          <div v-if="g.voices?.length" class="chips">
            <button v-for="v in g.voices" :key="v.name" class="chip" :title="v.kind" @click="emit('update:selected', v.name)">{{ v.name }}</button>
          </div>
        </article>
      </div>

      <template v-if="companies.length">
        <h4 class="block-title">{{ $t('analytics.briefCompanies') }}</h4>
        <p class="block-sub">{{ $t('analytics.briefCompaniesSub') }}</p>
        <div class="table-wrap companies">
          <table>
            <thead>
              <tr>
                <th>{{ $t('analytics.briefCompany') }}</th>
                <th>{{ $t('analytics.briefPosition') }}</th>
                <th>{{ $t('analytics.briefLikelyMove') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="c in companies" :key="c.name">
                <td><button class="author" @click="emit('update:selected', c.name)">{{ c.name }}</button><span class="kind">{{ c.kind }}</span></td>
                <td :class="{ fading: writing }">{{ c.position }}</td>
                <td :class="{ fading: writing }">{{ c.likely_move || '–' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </template>

      <div v-if="reading.watch?.length" class="watch">
        <h4>{{ $t('analytics.briefWatch') }}</h4>
        <ul><li v-for="(w, i) in reading.watch" :key="i">{{ w }}</li></ul>
      </div>

      <p class="foot">{{ $t('analytics.briefFoot') }}</p>
    </template>
  </section>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { fmt, pct } from './palette'

// The public site writes each run up once; rewriting on demand is turned off there.
const isPublic = import.meta.env.VITE_PUBLIC === '1'

const props = defineProps({
  briefing: { type: Object, default: null },
  writing: { type: Boolean, default: false },
  writeError: { type: String, default: '' },
  downloading: { type: Boolean, default: false }
})
const emit = defineEmits(['write', 'download', 'update:selected'])
const { t } = useI18n()

const openQuote = ref(null)
const facts = computed(() => props.briefing?.facts || {})
const reading = computed(() => props.briefing?.reading || {})
const confidence = computed(() => props.briefing?.confidence || { level: 'low', why: '' })
const finished = computed(() => !!facts.value.run?.finished)
const hasWriting = computed(() => (facts.value.run?.posts || 0) + (facts.value.run?.replies || 0) > 0)

const groups = computed(() => {
  const read = Object.fromEntries((reading.value.groups || []).map(g => [g.key, g]))
  return (facts.value.groups || []).map(g => ({ ...g, reading: read[g.key] || { stance: 'neutral', reaction: '' } }))
})
const companies = computed(() => {
  const kinds = Object.fromEntries((facts.value.companies || []).map(c => [c.name, c.kind]))
  return (reading.value.companies || []).map(c => ({ ...c, kind: kinds[c.name] || '' }))
})

const sourceClass = computed(() => {
  if (props.writing) return 'writing'
  return props.briefing?.reading_source === 'llm' ? 'llm' : finished.value ? 'quick' : 'live'
})
const sourceText = computed(() => {
  if (props.writing) return t('analytics.briefSourceWriting')
  if (props.briefing?.reading_source === 'llm') return t('analytics.briefSourceLlm')
  return finished.value ? t('analytics.briefSourceQuick') : t('analytics.briefSourceLive')
})
</script>

<style scoped>
.briefing { border-left: 4px solid var(--hm-signal); }
.head-actions { display: flex; align-items: center; gap: 10px; flex-shrink: 0; flex-wrap: wrap; justify-content: flex-end; }
.source {
  display: inline-flex; align-items: center; gap: 6px; font-family: var(--hm-font-mono); font-size: var(--hm-text-2xs);
  letter-spacing: 0.06em; text-transform: uppercase; color: var(--hm-ink-3); padding: 4px 10px;
  border-radius: var(--hm-radius-pill); background: var(--hm-surface-3);
}
.source-dot { width: 7px; height: 7px; border-radius: 50%; background: var(--hm-ink-5); }
.source.llm .source-dot { background: #1baf7a; }
.source.live .source-dot, .source.writing .source-dot { background: #eda100; animation: pulse 1.2s ease-in-out infinite; }
@keyframes pulse { 50% { opacity: 0.3; } }
@media (prefers-reduced-motion: reduce) { .source-dot { animation: none !important; } .fading { transition: none; } }
.fading { opacity: 0.45; transition: opacity var(--hm-duration) var(--hm-ease); }

.write-error { margin: 0 0 12px; padding: 8px 12px; border-radius: var(--hm-radius-md); background: var(--hm-danger-soft); color: var(--hm-danger); font-size: var(--hm-text-sm); }
.empty, .none { margin: 0; font-size: var(--hm-text-sm); color: var(--hm-ink-3); }

.eyebrow { margin: 4px 0 6px; font-family: var(--hm-font-mono); font-size: var(--hm-text-2xs); letter-spacing: 0.1em; text-transform: uppercase; color: var(--hm-signal-ink); }
.bottom-line {
  margin: 0 0 12px; font-family: var(--hm-font-display); font-size: var(--hm-text-xl); font-weight: 500;
  letter-spacing: var(--hm-tracking-display); line-height: var(--hm-leading-snug); color: var(--hm-ink); max-width: 70ch;
}
.cast-note { margin: -8px 0 16px; font-size: var(--hm-text-xs); color: var(--hm-ink-4); max-width: 100ch; }
.confidence { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin: 0 0 16px; font-size: var(--hm-text-xs); color: var(--hm-ink-4); max-width: 100ch; }

.tag {
  display: inline-block; padding: 2px 8px; border-radius: var(--hm-radius-sm); border: 1px solid currentColor;
  font-size: 11px; font-weight: 600; white-space: nowrap; color: var(--hm-ink-4); background: var(--hm-surface);
}
.conf-high, .str-strong, .stance-supportive { color: #17694b; }
.conf-medium, .str-moderate, .stance-cautious, .stance-divided { color: var(--hm-signal-ink); }
.conf-low, .stance-critical { color: var(--hm-danger); }

.means { margin: 0 0 20px; padding-left: 18px; font-size: var(--hm-text-base); line-height: var(--hm-leading-relaxed); color: var(--hm-ink); max-width: 85ch; }
.means li { margin-bottom: 4px; }
.means li::marker, .watch li::marker { color: var(--hm-signal); }

.two { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; margin-bottom: 24px; }
.panel { padding: 14px 16px; background: var(--hm-surface-2); border-radius: var(--hm-radius-md); }
.panel h4, .block-title, .watch h4 { margin: 0 0 10px; font-family: var(--hm-font-display); font-size: var(--hm-text-md); font-weight: 500; letter-spacing: -0.01em; color: var(--hm-ink); }
.point { padding: 10px 0; border-top: 1px solid var(--hm-line); }
.point:first-of-type { border-top: none; padding-top: 0; }
.point p { margin: 6px 0 0; font-size: var(--hm-text-sm); line-height: var(--hm-leading-relaxed); color: var(--hm-ink-2); }
.point .issue { margin-top: 0; font-weight: 600; color: var(--hm-ink); }
.point .held { font-size: 11px; color: var(--hm-ink-4); }

.block-title { margin-bottom: 2px; }
.block-sub { margin: 0 0 12px; font-size: var(--hm-text-xs); color: var(--hm-ink-4); }
.groups { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 12px; margin-bottom: 24px; }
.group { padding: 14px 16px; border: 1px solid var(--hm-line); border-radius: var(--hm-radius-md); background: var(--hm-surface); min-width: 0; }
.group.quiet { background: var(--hm-surface-2); }
.group header { display: flex; justify-content: space-between; align-items: center; gap: 8px; margin-bottom: 4px; }
.group h5 { margin: 0; font-size: var(--hm-text-base); font-weight: 600; color: var(--hm-ink); }
.meta { margin: 0 0 6px; font-size: 11px; color: var(--hm-ink-4); font-variant-numeric: tabular-nums; }
.reception { display: flex; align-items: center; gap: 8px; margin: 0 0 8px; font-size: 11px; color: var(--hm-ink-4); }
.rec-bar { display: inline-block; width: 56px; height: 6px; border-radius: 3px; background: #eb6834; overflow: hidden; flex-shrink: 0; }
.rec-bar span { display: block; height: 100%; background: #2a78d6; }
.reaction, .next { margin: 0 0 8px; font-size: var(--hm-text-sm); line-height: var(--hm-leading-relaxed); color: var(--hm-ink-2); }
.next strong { color: var(--hm-ink); }

.quote { margin: 0 0 8px; padding: 8px 12px; border-left: 3px solid var(--hm-line-strong); background: var(--hm-surface-2); border-radius: 0 var(--hm-radius-sm) var(--hm-radius-sm) 0; }
.quote p {
  margin: 0 0 6px; font-size: 12.5px; line-height: 1.5; color: var(--hm-ink); cursor: pointer;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
}
.quote p.open { display: block; -webkit-line-clamp: unset; }
.quote footer { display: flex; flex-wrap: wrap; gap: 4px; font-size: 11px; color: var(--hm-ink-4); }
.author { background: none; border: none; padding: 0; font: inherit; font-weight: 600; color: var(--hm-ink); cursor: pointer; text-align: left; }
.author:hover { text-decoration: underline; }
.chips { display: flex; flex-wrap: wrap; gap: 6px; }
.chip {
  font: inherit; font-size: 11px; padding: 3px 9px; border-radius: var(--hm-radius-pill); background: var(--hm-surface-3);
  border: 1px solid transparent; color: var(--hm-ink); cursor: pointer;
}
.chip:hover { border-color: var(--hm-line-strong); background: var(--hm-surface); }

.companies { max-height: 460px; margin-bottom: 24px; }
.companies th, .companies td { text-align: left !important; vertical-align: top; white-space: normal; line-height: 1.5; font-size: 12.5px; }
.companies td:first-child { width: 170px; }
.kind { display: block; font-size: 11px; color: var(--hm-ink-4); }

.watch { padding: 14px 16px; background: var(--hm-surface-2); border-radius: var(--hm-radius-md); margin-bottom: 14px; }
.watch ul { margin: 0; padding-left: 18px; font-size: var(--hm-text-sm); line-height: var(--hm-leading-relaxed); color: var(--hm-ink); }
.foot { margin: 0; font-size: 11px; line-height: 1.5; color: var(--hm-ink-4); max-width: 100ch; }

@media (max-width: 900px) {
  .two { grid-template-columns: 1fr; }
  .card-head { flex-direction: column; }
  .head-actions { justify-content: flex-start; }
}
</style>
