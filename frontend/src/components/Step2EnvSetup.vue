<template>
  <div class="env-setup-panel">
    <div class="scroll-container">
      <!-- Step 01: Simulation instance -->
      <div class="step-card" :class="{ 'active': phase === 0, 'completed': phase > 0 }">
        <div class="card-header">
          <div class="step-info">
            <span class="step-num">01</span>
            <span class="step-title">{{ $t('step2.simInstanceInit') }}</span>
          </div>
          <div class="step-status">
            <span v-if="phase > 0" class="badge success">{{ $t('common.completed') }}</span>
            <span v-else class="badge processing">{{ $t('step2.initializing') }}</span>
          </div>
        </div>
        
        <div class="card-content">
          <p class="api-note">POST /api/simulation/create</p>
          <p class="description">
            {{ $t('step2.simInstanceDesc') }}
          </p>

          <div v-if="simulationId" class="info-card">
            <div class="info-row">
              <span class="info-label">Project ID</span>
              <span class="info-value mono">{{ projectData?.project_id }}</span>
            </div>
            <div class="info-row">
              <span class="info-label">Graph ID</span>
              <span class="info-value mono">{{ projectData?.graph_id }}</span>
            </div>
            <div class="info-row">
              <span class="info-label">Simulation ID</span>
              <span class="info-value mono">{{ simulationId }}</span>
            </div>
            <div class="info-row">
              <span class="info-label">Task ID</span>
              <span class="info-value mono">{{ taskId || $t('step2.asyncTaskDone') }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Step 02: Generate agent profiles -->
      <div class="step-card" :class="{ 'active': phase === 1, 'completed': phase > 1 }">
        <div class="card-header">
          <div class="step-info">
            <span class="step-num">02</span>
            <span class="step-title">{{ $t('step2.generateAgentPersona') }}</span>
          </div>
          <div class="step-status">
            <span v-if="phase > 1" class="badge success">{{ $t('common.completed') }}</span>
            <span v-else-if="phase === 1" class="badge processing">{{ prepareProgress }}%</span>
            <span v-else class="badge pending">{{ $t('common.pending') }}</span>
          </div>
        </div>

        <div class="card-content">
          <p class="api-note">POST /api/simulation/prepare</p>
          <p class="description">
            {{ $t('step2.generateAgentPersonaDesc') }}
          </p>

          <!-- Hivemind: the cast as a tree, filling in as each persona is written -->
          <div v-if="simulationId && (phase >= 1 || profiles.length > 0)" class="hm-analytics cast-embed">
            <CastTree :simulation-id="simulationId" />
          </div>

          <!-- Profiles Stats -->
          <div v-if="profiles.length > 0" class="stats-grid">
            <div class="stat-card">
              <span class="stat-value">{{ profiles.length }}</span>
              <span class="stat-label">{{ $t('step2.currentAgentCount') }}</span>
            </div>
            <div class="stat-card">
              <span class="stat-value">{{ expectedTotal || '-' }}</span>
              <span class="stat-label">{{ $t('step2.expectedAgentTotal') }}</span>
            </div>
            <div class="stat-card">
              <span class="stat-value">{{ totalTopicsCount }}</span>
              <span class="stat-label">{{ $t('step2.relatedTopicsCount') }}</span>
            </div>
          </div>

          <!-- Profiles List Preview -->
          <div v-if="profiles.length > 0" class="profiles-preview">
            <div class="preview-header">
              <span class="preview-title">{{ $t('step2.generatedAgentPersonas') }}</span>
            </div>
            <div class="profiles-list">
              <div 
                v-for="(profile, idx) in profiles" 
                :key="idx" 
                class="profile-card"
                @click="selectProfile(profile)"
              >
                <div class="profile-header">
                  <span class="profile-realname">{{ profile.username || 'Unknown' }}</span>
                  <span class="profile-username">@{{ profile.name || `agent_${idx}` }}</span>
                </div>
                <div class="profile-meta">
                  <span class="profile-profession">{{ profile.profession || $t('step2.unknownProfession') }}</span>
                </div>
                <p class="profile-bio">{{ profile.bio || $t('step2.noBio') }}</p>
                <div v-if="profile.interested_topics?.length" class="profile-topics">
                  <span 
                    v-for="topic in profile.interested_topics.slice(0, 3)" 
                    :key="topic" 
                    class="topic-tag"
                  >{{ topic }}</span>
                  <span v-if="profile.interested_topics.length > 3" class="topic-more">
                    +{{ profile.interested_topics.length - 3 }}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Step 03: Generate the dual-platform simulation config -->
      <div class="step-card" :class="{ 'active': phase === 2, 'completed': phase > 2 }">
        <div class="card-header">
          <div class="step-info">
            <span class="step-num">03</span>
            <span class="step-title">{{ $t('step2.dualPlatformConfig') }}</span>
          </div>
          <div class="step-status">
            <span v-if="phase > 2" class="badge success">{{ $t('common.completed') }}</span>
            <span v-else-if="phase === 2" class="badge processing">{{ $t('step2.generating') }}</span>
            <span v-else class="badge pending">{{ $t('common.pending') }}</span>
          </div>
        </div>

        <div class="card-content">
          <p class="api-note">POST /api/simulation/prepare</p>
          <p class="description">
            {{ $t('step2.dualPlatformConfigDesc') }}
          </p>
          
          <!-- Config Preview -->
          <div v-if="simulationConfig" class="config-detail-panel">
            <!-- Time config -->
            <div class="config-block">
              <div class="config-grid">
                <div class="config-item">
                  <span class="config-item-label">{{ $t('step2.simulationDuration') }}</span>
                  <span class="config-item-value">{{ simulationConfig.time_config?.total_simulation_hours || '-' }} {{ $t('common.hours') }}</span>
                </div>
                <div class="config-item">
                  <span class="config-item-label">{{ $t('step2.roundDuration') }}</span>
                  <span class="config-item-value">{{ simulationConfig.time_config?.minutes_per_round || '-' }} {{ $t('common.minutes') }}</span>
                </div>
                <div class="config-item">
                  <span class="config-item-label">{{ $t('step2.totalRounds') }}</span>
                  <span v-if="publicCap && plannedRounds > publicCap" class="config-item-value">{{ $t('step2.roundsCapped', { rounds: publicCap, planned: plannedRounds }) }}</span>
                  <span v-else class="config-item-value">{{ plannedRounds || '-' }} {{ $t('common.rounds') }}</span>
                </div>
                <div class="config-item">
                  <span class="config-item-label">{{ $t('step2.activePerHour') }}</span>
                  <span class="config-item-value">{{ simulationConfig.time_config?.agents_per_hour_min }}-{{ simulationConfig.time_config?.agents_per_hour_max }}</span>
                </div>
              </div>
              <div class="time-periods">
                <div class="period-item">
                  <span class="period-label">{{ $t('step2.peakHours') }}</span>
                  <span class="period-hours">{{ simulationConfig.time_config?.peak_hours?.join(':00, ') }}:00</span>
                  <span class="period-multiplier">×{{ simulationConfig.time_config?.peak_activity_multiplier }}</span>
                </div>
                <div class="period-item">
                  <span class="period-label">{{ $t('step2.workHours') }}</span>
                  <span class="period-hours">{{ simulationConfig.time_config?.work_hours?.[0] }}:00-{{ simulationConfig.time_config?.work_hours?.slice(-1)[0] }}:00</span>
                  <span class="period-multiplier">×{{ simulationConfig.time_config?.work_activity_multiplier }}</span>
                </div>
                <div class="period-item">
                  <span class="period-label">{{ $t('step2.morningHours') }}</span>
                  <span class="period-hours">{{ simulationConfig.time_config?.morning_hours?.[0] }}:00-{{ simulationConfig.time_config?.morning_hours?.slice(-1)[0] }}:00</span>
                  <span class="period-multiplier">×{{ simulationConfig.time_config?.morning_activity_multiplier }}</span>
                </div>
                <div class="period-item">
                  <span class="period-label">{{ $t('step2.offPeakHours') }}</span>
                  <span class="period-hours">{{ simulationConfig.time_config?.off_peak_hours?.[0] }}:00-{{ simulationConfig.time_config?.off_peak_hours?.slice(-1)[0] }}:00</span>
                  <span class="period-multiplier">×{{ simulationConfig.time_config?.off_peak_activity_multiplier }}</span>
                </div>
              </div>
            </div>

            <!-- Agent config -->
            <div class="config-block">
              <div class="config-block-header">
                <span class="config-block-title">{{ $t('step2.agentConfig') }}</span>
                <span class="config-block-badge">{{ simulationConfig.agent_configs?.length || 0 }} {{ $t('common.items') }}</span>
              </div>
              <div class="agents-cards">
                <div 
                  v-for="agent in simulationConfig.agent_configs" 
                  :key="agent.agent_id" 
                  class="agent-card"
                >
                  <!-- Card header -->
                  <div class="agent-card-header">
                    <div class="agent-identity">
                      <span class="agent-id">Agent {{ agent.agent_id }}</span>
                      <span class="agent-name">{{ agent.entity_name }}</span>
                    </div>
                    <div class="agent-tags">
                      <span class="agent-type">{{ agent.entity_type }}</span>
                      <span class="agent-stance" :class="'stance-' + agent.stance">{{ agent.stance }}</span>
                    </div>
                  </div>
                  
                  <!-- Activity timeline -->
                  <div class="agent-timeline">
                    <span class="timeline-label">{{ $t('step2.activeTimePeriod') }}</span>
                    <div class="mini-timeline">
                      <div 
                        v-for="hour in 24" 
                        :key="hour - 1" 
                        class="timeline-hour"
                        :class="{ 'active': agent.active_hours?.includes(hour - 1) }"
                        :title="`${hour - 1}:00`"
                      ></div>
                    </div>
                    <div class="timeline-marks">
                      <span>0</span>
                      <span>6</span>
                      <span>12</span>
                      <span>18</span>
                      <span>24</span>
                    </div>
                  </div>

                  <!-- Behaviour parameters -->
                  <div class="agent-params">
                    <div class="param-group">
                      <div class="param-item">
                        <span class="param-label">{{ $t('step2.postsPerHour') }}</span>
                        <span class="param-value">{{ agent.posts_per_hour }}</span>
                      </div>
                      <div class="param-item">
                        <span class="param-label">{{ $t('step2.commentsPerHour') }}</span>
                        <span class="param-value">{{ agent.comments_per_hour }}</span>
                      </div>
                      <div class="param-item">
                        <span class="param-label">{{ $t('step2.responseDelay') }}</span>
                        <span class="param-value">{{ agent.response_delay_min }}-{{ agent.response_delay_max }}min</span>
                      </div>
                    </div>
                    <div class="param-group">
                      <div class="param-item">
                        <span class="param-label">{{ $t('step2.activityLevel') }}</span>
                        <span class="param-value with-bar">
                          <span class="mini-bar" :style="{ width: (agent.activity_level * 100) + '%' }"></span>
                          {{ (agent.activity_level * 100).toFixed(0) }}%
                        </span>
                      </div>
                      <div class="param-item">
                        <span class="param-label">{{ $t('step2.sentimentBias') }}</span>
                        <span class="param-value" :class="agent.sentiment_bias > 0 ? 'positive' : agent.sentiment_bias < 0 ? 'negative' : 'neutral'">
                          {{ agent.sentiment_bias > 0 ? '+' : '' }}{{ agent.sentiment_bias?.toFixed(1) }}
                        </span>
                      </div>
                      <div class="param-item">
                        <span class="param-label">{{ $t('step2.influenceWeight') }}</span>
                        <span class="param-value highlight">{{ agent.influence_weight?.toFixed(1) }}</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- Platform config -->
            <div class="config-block">
              <div class="config-block-header">
                <span class="config-block-title">{{ $t('step2.recommendAlgoConfig') }}</span>
              </div>
              <div class="platforms-grid">
                <div v-if="simulationConfig.twitter_config" class="platform-card">
                  <div class="platform-card-header">
                    <span class="platform-name">{{ $t('step2.platform1Name') }}</span>
                  </div>
                  <div class="platform-params">
                    <div class="param-row">
                      <span class="param-label">{{ $t('step2.recencyWeight') }}</span>
                      <span class="param-value">{{ simulationConfig.twitter_config.recency_weight }}</span>
                    </div>
                    <div class="param-row">
                      <span class="param-label">{{ $t('step2.popularityWeight') }}</span>
                      <span class="param-value">{{ simulationConfig.twitter_config.popularity_weight }}</span>
                    </div>
                    <div class="param-row">
                      <span class="param-label">{{ $t('step2.relevanceWeight') }}</span>
                      <span class="param-value">{{ simulationConfig.twitter_config.relevance_weight }}</span>
                    </div>
                    <div class="param-row">
                      <span class="param-label">{{ $t('step2.viralThreshold') }}</span>
                      <span class="param-value">{{ simulationConfig.twitter_config.viral_threshold }}</span>
                    </div>
                    <div class="param-row">
                      <span class="param-label">{{ $t('step2.echoChamberStrength') }}</span>
                      <span class="param-value">{{ simulationConfig.twitter_config.echo_chamber_strength }}</span>
                    </div>
                  </div>
                </div>
                <div v-if="simulationConfig.reddit_config" class="platform-card">
                  <div class="platform-card-header">
                    <span class="platform-name">{{ $t('step2.platform2Name') }}</span>
                  </div>
                  <div class="platform-params">
                    <div class="param-row">
                      <span class="param-label">{{ $t('step2.recencyWeight') }}</span>
                      <span class="param-value">{{ simulationConfig.reddit_config.recency_weight }}</span>
                    </div>
                    <div class="param-row">
                      <span class="param-label">{{ $t('step2.popularityWeight') }}</span>
                      <span class="param-value">{{ simulationConfig.reddit_config.popularity_weight }}</span>
                    </div>
                    <div class="param-row">
                      <span class="param-label">{{ $t('step2.relevanceWeight') }}</span>
                      <span class="param-value">{{ simulationConfig.reddit_config.relevance_weight }}</span>
                    </div>
                    <div class="param-row">
                      <span class="param-label">{{ $t('step2.viralThreshold') }}</span>
                      <span class="param-value">{{ simulationConfig.reddit_config.viral_threshold }}</span>
                    </div>
                    <div class="param-row">
                      <span class="param-label">{{ $t('step2.echoChamberStrength') }}</span>
                      <span class="param-value">{{ simulationConfig.reddit_config.echo_chamber_strength }}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- LLM config reasoning -->
            <div v-if="simulationConfig.generation_reasoning" class="config-block">
              <div class="config-block-header">
                <span class="config-block-title">{{ $t('step2.llmConfigReasoning') }}</span>
              </div>
              <div class="reasoning-content">
                <div 
                  v-for="(reason, idx) in simulationConfig.generation_reasoning.split('|').slice(0, 2)" 
                  :key="idx" 
                  class="reasoning-item"
                >
                  <p class="reasoning-text">{{ reason.trim() }}</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Step 04: Initial activation plan -->
      <div class="step-card" :class="{ 'active': phase === 3, 'completed': phase > 3 }">
        <div class="card-header">
          <div class="step-info">
            <span class="step-num">04</span>
            <span class="step-title">{{ $t('step2.initialActivation') }}</span>
          </div>
          <div class="step-status">
            <span v-if="phase > 3" class="badge success">{{ $t('common.completed') }}</span>
            <span v-else-if="phase === 3" class="badge processing">{{ $t('step2.orchestrating') }}</span>
            <span v-else class="badge pending">{{ $t('common.pending') }}</span>
          </div>
        </div>

        <div class="card-content">
          <p class="api-note">POST /api/simulation/prepare</p>
          <p class="description">
            {{ $t('step2.initialActivationDesc') }}
          </p>

          <div v-if="simulationConfig?.event_config" class="orchestration-content">
            <!-- Narrative direction -->
            <div class="narrative-box">
              <span class="box-label narrative-label">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" class="special-icon">
                  <path d="M12 22C17.5228 22 22 17.5228 22 12C22 6.47715 17.5228 2 12 2C6.47715 2 2 6.47715 2 12C2 17.5228 6.47715 22 12 22Z" stroke="url(#paint0_linear)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
                  <path d="M16.24 7.76L14.12 14.12L7.76 16.24L9.88 9.88L16.24 7.76Z" fill="url(#paint0_linear)" stroke="url(#paint0_linear)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
                  <defs>
                    <linearGradient id="paint0_linear" x1="2" y1="2" x2="22" y2="22" gradientUnits="userSpaceOnUse">
                      <stop stop-color="#F0A818"/>
                      <stop offset="1" stop-color="#D4890A"/>
                    </linearGradient>
                  </defs>
                </svg>
                {{ $t('step2.narrativeDirection') }}
              </span>
              <p class="narrative-text">{{ simulationConfig.event_config.narrative_direction }}</p>
            </div>

            <!-- Hot topics -->
            <div class="topics-section">
              <span class="box-label">{{ $t('step2.initialHotTopics') }}</span>
              <div class="hot-topics-grid">
                <span v-for="topic in simulationConfig.event_config.hot_topics" :key="topic" class="hot-topic-tag">
                  # {{ topic }}
                </span>
              </div>
            </div>

            <!-- Initial post stream -->
            <div class="initial-posts-section">
              <span class="box-label">{{ $t('step2.initialActivationSeq', { count: simulationConfig.event_config.initial_posts.length }) }}</span>
              <div class="posts-timeline">
                <div v-for="(post, idx) in simulationConfig.event_config.initial_posts" :key="idx" class="timeline-item">
                  <div class="timeline-marker"></div>
                  <div class="timeline-content">
                    <div class="post-header">
                      <span class="post-role">{{ post.poster_type }}</span>
                      <span class="post-agent-info">
                        <span class="post-id">Agent {{ post.poster_agent_id }}</span>
                        <span class="post-username">@{{ getAgentUsername(post.poster_agent_id) }}</span>
                      </span>
                    </div>
                    <p class="post-text">{{ post.content }}</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Step 05: Setup complete -->
      <div class="step-card" :class="{ 'active': phase === 4 }">
        <div class="card-header">
          <div class="step-info">
            <span class="step-num">05</span>
            <span class="step-title">{{ $t('step2.setupComplete') }}</span>
          </div>
          <div class="step-status">
            <span v-if="phase >= 4" class="badge processing">{{ $t('step1.inProgress') }}</span>
            <span v-else class="badge pending">{{ $t('common.pending') }}</span>
          </div>
        </div>

        <div class="card-content">
          <p class="api-note">POST /api/simulation/start</p>
          <p class="description">{{ $t('step2.setupCompleteDesc') }}</p>
          
          <!-- Round count settings: only shown once the config is generated and the round count is known -->
          <div v-if="simulationConfig && publicCap" class="rounds-config-section">
            <div class="rounds-header">
              <div class="header-left">
                <span class="section-title">{{ $t('step2.roundsConfig') }}</span>
                <span class="section-desc">{{ $t('step2.publicRoundsDesc', { rounds: publicCap, hours: Math.round(publicCap * (simulationConfig?.time_config?.minutes_per_round || 60) / 60), planned: simulationConfig?.time_config?.total_simulation_hours || '-' }) }}</span>
              </div>
            </div>
            <div class="rounds-content auto">
              <div class="auto-info-card">
                <div class="auto-value">
                  <span class="val-num">{{ publicCap }}</span>
                  <span class="val-unit">{{ $t('step2.roundsUnit') }}</span>
                </div>
                <div class="auto-content">
                  <div class="auto-desc"><p>{{ $t('step2.publicRoundsNote') }}</p></div>
                </div>
              </div>
            </div>
          </div>
          <div v-else-if="simulationConfig && autoGeneratedRounds" class="rounds-config-section">
            <div class="rounds-header">
              <div class="header-left">
                <span class="section-title">{{ $t('step2.roundsConfig') }}</span>
                <span class="section-desc">{{ $t('step2.roundsConfigDesc', { hours: simulationConfig?.time_config?.total_simulation_hours || '-', minutesPerRound: simulationConfig?.time_config?.minutes_per_round || '-' }) }}</span>
              </div>
              <label class="switch-control">
                <input type="checkbox" v-model="useCustomRounds">
                <span class="switch-track"></span>
                <span class="switch-label">{{ $t('step2.customToggle') }}</span>
              </label>
            </div>
            
            <Transition name="fade" mode="out-in">
              <div v-if="useCustomRounds" class="rounds-content custom" key="custom">
                <div class="slider-display">
                  <div class="slider-main-value">
                    <span class="val-num">{{ customMaxRounds }}</span>
                    <span class="val-unit">{{ $t('step2.roundsUnit') }}</span>
                  </div>
                  <div class="slider-meta-info">
                    <span>{{ $t('step2.estimatedDuration', { minutes: Math.round(customMaxRounds * 0.6) }) }}</span>
                  </div>
                </div>

                <div class="range-wrapper">
                  <input 
                    type="range" 
                    v-model.number="customMaxRounds" 
                    min="10" 
                    :max="autoGeneratedRounds"
                    step="5"
                    class="minimal-slider"
                    :style="{ '--percent': ((customMaxRounds - 10) / (autoGeneratedRounds - 10)) * 100 + '%' }"
                  />
                  <div class="range-marks">
                    <span>10</span>
                    <span 
                      class="mark-recommend" 
                      :class="{ active: customMaxRounds === 40 }"
                      @click="customMaxRounds = 40"
                      :style="{ position: 'absolute', left: `calc(${(40 - 10) / (autoGeneratedRounds - 10) * 100}% - 30px)` }"
                    >{{ $t('step2.recommendedRounds', { rounds: 40 }) }}</span>
                    <span>{{ autoGeneratedRounds }}</span>
                  </div>
                </div>
              </div>
              
              <div v-else class="rounds-content auto" key="auto">
                <div class="auto-info-card">
                  <div class="auto-value">
                    <span class="val-num">{{ autoGeneratedRounds }}</span>
                    <span class="val-unit">{{ $t('step2.roundsUnit') }}</span>
                  </div>
                  <div class="auto-content">
                    <div class="auto-meta-row">
                      <span class="duration-badge">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                          <circle cx="12" cy="12" r="10"></circle>
                          <polyline points="12 6 12 12 16 14"></polyline>
                        </svg>
                        {{ $t('step2.estimatedDurationFull', { minutes: Math.round(autoGeneratedRounds * 0.6) }) }}
                      </span>
                    </div>
                    <div class="auto-desc">
                      <p class="highlight-tip" @click="useCustomRounds = true">{{ $t('step2.customTip') }} →</p>
                    </div>
                  </div>
                </div>
              </div>
            </Transition>
          </div>

          <div class="action-group dual">
            <button 
              class="action-btn secondary"
              @click="$emit('go-back')"
            >
              ← {{ $t('step2.backToGraphBuild') }}
            </button>
            <button 
              class="action-btn primary"
              :disabled="phase < 4"
              @click="handleStartSimulation"
            >
              {{ $t('step2.startDualWorldSim') }} →
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Profile Detail Modal -->
    <Transition name="modal">
      <div v-if="selectedProfile" class="profile-modal-overlay" @click.self="selectedProfile = null">
        <div class="profile-modal" role="dialog" aria-modal="true">
          <div class="modal-header">
          <div class="modal-header-info">
            <div class="modal-name-row">
              <span class="modal-realname">{{ selectedProfile.username }}</span>
              <span class="modal-username">@{{ selectedProfile.name }}</span>
            </div>
            <span class="modal-profession">{{ selectedProfile.profession }}</span>
          </div>
          <button class="close-btn" aria-label="Close" @click="selectedProfile = null">
            <svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true"><path d="M4 4l8 8M12 4l-8 8" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>
          </button>
        </div>
        
        <div class="modal-body">
          <!-- Basic info -->
          <div class="modal-info-grid">
            <div class="info-item">
              <span class="info-label">{{ $t('step2.profileModalAge') }}</span>
              <span class="info-value">{{ selectedProfile.age || '-' }} {{ $t('step2.yearsOld') }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">{{ $t('step2.profileModalGender') }}</span>
              <span class="info-value">{{ { male: $t('step2.genderMale'), female: $t('step2.genderFemale'), other: $t('step2.genderOther') }[selectedProfile.gender] || selectedProfile.gender }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">{{ $t('step2.profileModalCountry') }}</span>
              <span class="info-value">{{ selectedProfile.country || '-' }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">{{ $t('step2.profileModalMbti') }}</span>
              <span class="info-value mbti">{{ selectedProfile.mbti || '-' }}</span>
            </div>
          </div>

          <!-- Bio -->
          <div class="modal-section">
            <span class="section-label">{{ $t('step2.profileModalBio') }}</span>
            <p class="section-bio">{{ selectedProfile.bio || $t('step2.noBio') }}</p>
          </div>

          <!-- Topics of interest -->
          <div class="modal-section" v-if="selectedProfile.interested_topics?.length">
            <span class="section-label">{{ $t('step2.profileModalTopics') }}</span>
            <div class="topics-grid">
              <span 
                v-for="topic in selectedProfile.interested_topics" 
                :key="topic" 
                class="topic-item"
              >{{ topic }}</span>
            </div>
          </div>

          <!-- Full persona -->
          <div class="modal-section" v-if="selectedProfile.persona">
            <span class="section-label">{{ $t('step2.profileModalPersona') }}</span>
            
            <!-- Persona dimensions overview -->
            <div class="persona-dimensions">
              <div class="dimension-card">
                <span class="dim-title">{{ $t('step2.personaDimExperience') }}</span>
                <span class="dim-desc">{{ $t('step2.personaDimExperienceDesc') }}</span>
              </div>
              <div class="dimension-card">
                <span class="dim-title">{{ $t('step2.personaDimBehavior') }}</span>
                <span class="dim-desc">{{ $t('step2.personaDimBehaviorDesc') }}</span>
              </div>
              <div class="dimension-card">
                <span class="dim-title">{{ $t('step2.personaDimMemory') }}</span>
                <span class="dim-desc">{{ $t('step2.personaDimMemoryDesc') }}</span>
              </div>
              <div class="dimension-card">
                <span class="dim-title">{{ $t('step2.personaDimSocial') }}</span>
                <span class="dim-desc">{{ $t('step2.personaDimSocialDesc') }}</span>
              </div>
            </div>

            <div class="persona-content">
              <p class="section-persona">{{ selectedProfile.persona }}</p>
            </div>
          </div>
        </div>
      </div>
      </div>
    </Transition>

    <!-- Bottom Info / Logs -->
    <div class="system-logs">
      <div class="log-header">
        <span class="log-title">SYSTEM DASHBOARD</span>
        <span class="log-id">{{ simulationId || 'NO_SIMULATION' }}</span>
      </div>
      <div class="log-content" ref="logContent">
        <div class="log-line" v-for="(log, idx) in systemLogs" :key="idx">
          <span class="log-time">{{ log.time }}</span>
          <span class="log-msg">{{ log.msg }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import CastTree from './analytics/CastTree.vue'
import service from '../api/index.js'
import {
  prepareSimulation,
  getPrepareStatus,
  getSimulationProfilesRealtime,
  getSimulationConfig,
  getSimulationConfigRealtime
} from '../api/simulation'

const { t } = useI18n()

const props = defineProps({
  simulationId: String,  // passed in by the parent component
  projectData: Object,
  graphData: Object,
  systemLogs: Array
})

const emit = defineEmits(['go-back', 'next-step', 'add-log', 'update-status'])

// State
const phase = ref(0) // 0: initialising, 1: generating profiles, 2: generating config, 3: done
const taskId = ref(null)
const prepareProgress = ref(0)
const currentStage = ref('')
const progressMessage = ref('')
const profiles = ref([])
const entityTypes = ref([])
const expectedTotal = ref(null)
const simulationConfig = ref(null)
const selectedProfile = ref(null)
const showProfilesDetail = ref(true)

// Log de-duplication: remember the key details of the last line logged
let lastLoggedMessage = ''
let lastLoggedProfileCount = 0
let lastLoggedConfigStage = ''

// Round count settings
const useCustomRounds = ref(false) // use the automatically configured round count by default
const customMaxRounds = ref(40)   // 40 rounds recommended by default

// Watch stage to update phase. currentStage holds the backend's localised stage
// name, so the Chinese names below are what it sends when the locale is Chinese
// (locales/zh.json progress.generatingProfiles / generatingSimConfig / preparingScripts).
watch(currentStage, (newStage) => {
  if (newStage === '生成Agent人设' || newStage === 'generating_profiles') {
    phase.value = 1
  } else if (newStage === '生成模拟配置' || newStage === 'generating_config') {
    phase.value = 2
    // Config generation has started: begin polling the config
    if (!configTimer) {
      addLog(t('log.startGeneratingConfig'))
      startConfigPolling()
    }
  } else if (newStage === '准备模拟脚本' || newStage === 'copying_scripts') {
    phase.value = 2 // still part of the config phase
  }
})

// Rounds the generated schedule asks for (hours x 60 / minutes per round)
const plannedRounds = computed(() => {
  const tc = simulationConfig.value?.time_config
  if (!tc?.total_simulation_hours || !tc?.minutes_per_round) return null
  return Math.floor((tc.total_simulation_hours * 60) / tc.minutes_per_round)
})

// Public site: the server plays at most this many rounds, so show that instead of a picker
const isPublic = import.meta.env.VITE_PUBLIC === '1'
const publicCap = ref(null)
const loadPublicCap = async () => {
  if (!isPublic) return
  try {
    const res = await service.get('/api/public/status')
    publicCap.value = res.data?.max_rounds || null
  } catch {
    publicCap.value = null
  }
}

// Work out the generated round count from the config (no hard-coded default)
const autoGeneratedRounds = computed(() => {
  if (!simulationConfig.value?.time_config) {
    return null // null until the config has been generated
  }
  const totalHours = simulationConfig.value.time_config.total_simulation_hours
  const minutesPerRound = simulationConfig.value.time_config.minutes_per_round
  if (!totalHours || !minutesPerRound) {
    return null // null when the config data is incomplete
  }
  const calculatedRounds = Math.floor((totalHours * 60) / minutesPerRound)
  // Keep the maximum at 40 rounds or more (the recommended value) so the slider range stays valid
  return Math.max(calculatedRounds, 40)
})

// Polling timer
let pollTimer = null
let profilesTimer = null
let configTimer = null

// Computed
const displayProfiles = computed(() => {
  if (showProfilesDetail.value) {
    return profiles.value
  }
  return profiles.value.slice(0, 6)
})

// Look up the username for an agent_id
const getAgentUsername = (agentId) => {
  if (profiles.value && profiles.value.length > agentId && agentId >= 0) {
    const profile = profiles.value[agentId]
    return profile?.username || `agent_${agentId}`
  }
  return `agent_${agentId}`
}

// Total number of topics across all profiles
const totalTopicsCount = computed(() => {
  return profiles.value.reduce((sum, p) => {
    return sum + (p.interested_topics?.length || 0)
  }, 0)
})

// Methods
const addLog = (msg) => {
  emit('add-log', msg)
}

const handlePrepareFailure = (message) => {
  stopPolling()
  stopProfilesPolling()
  stopConfigPolling()
  addLog(t('log.prepareFailedWithError', { error: message || t('common.unknownError') }))
  emit('update-status', 'error')
}

// Handle a click on the start-simulation button
const handleStartSimulation = () => {
  // Build the parameters passed to the parent component
  const params = {}
  
  if (useCustomRounds.value) {
    // The user chose a custom round count: pass max_rounds
    params.maxRounds = customMaxRounds.value
    addLog(t('log.startSimCustomRounds', { rounds: customMaxRounds.value }))
  } else {
    // The user kept the generated round count: do not pass max_rounds
    addLog(t('log.startSimAutoRounds', { rounds: autoGeneratedRounds.value }))
  }
  
  emit('next-step', params)
}

const truncateBio = (bio) => {
  if (bio.length > 80) {
    return bio.substring(0, 80) + '...'
  }
  return bio
}

const selectProfile = (profile) => {
  selectedProfile.value = profile
}

// Start preparing the simulation automatically
const startPrepareSimulation = async () => {
  if (!props.simulationId) {
    addLog(t('log.errorMissingSimId'))
    emit('update-status', 'error')
    return
  }
  
  // Mark step one done and start step two
  phase.value = 1
  addLog(t('log.simInstanceCreated', { id: props.simulationId }))
  addLog(t('log.preparingSimEnv'))
  emit('update-status', 'processing')
  
  try {
    const res = await prepareSimulation({
      simulation_id: props.simulationId,
      use_llm_for_profiles: true,
      parallel_profile_count: 5
    })
    
    if (res.success && res.data) {
      if (res.data.already_prepared) {
        addLog(t('log.detectedExistingPrep'))
        await loadPreparedData()
        return
      }
      
      taskId.value = res.data.task_id
      addLog(t('log.prepareTaskStarted'))
      addLog(t('log.prepareTaskId', { taskId: res.data.task_id }))
      
      // Set the expected agent total straight away (from the prepare endpoint response)
      if (res.data.expected_entities_count) {
        expectedTotal.value = res.data.expected_entities_count
        addLog(t('log.zepEntitiesFound', { count: res.data.expected_entities_count }))
        if (res.data.entity_types && res.data.entity_types.length > 0) {
          addLog(t('log.entityTypes', { types: res.data.entity_types.join(', ') }))
        }
      }
      
      addLog(t('log.startPollingProgress'))
      // Start polling progress
      startPolling()
      // Start fetching profiles in real time
      startProfilesPolling()
    } else {
      addLog(t('log.prepareFailed', { error: res.error || t('common.unknownError') }))
      emit('update-status', 'error')
    }
  } catch (err) {
    addLog(t('log.prepareException', { error: err.message }))
    emit('update-status', 'error')
  }
}

const startPolling = () => {
  pollTimer = setInterval(pollPrepareStatus, 2000)
}

const stopPolling = () => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

const startProfilesPolling = () => {
  profilesTimer = setInterval(fetchProfilesRealtime, 3000)
}

const stopProfilesPolling = () => {
  if (profilesTimer) {
    clearInterval(profilesTimer)
    profilesTimer = null
  }
}

const pollPrepareStatus = async () => {
  if (!taskId.value && !props.simulationId) return
  
  try {
    const res = await getPrepareStatus({
      task_id: taskId.value,
      simulation_id: props.simulationId
    })
    
    if (res.success && res.data) {
      const data = res.data
      
      // Update progress
      prepareProgress.value = data.progress || 0
      progressMessage.value = data.message || ''
      
      // Parse the stage info and log the details
      if (data.progress_detail) {
        currentStage.value = data.progress_detail.current_stage_name || ''
        
        // Log detailed progress (without repeats)
        const detail = data.progress_detail
        const logKey = `${detail.current_stage}-${detail.current_item}-${detail.total_items}`
        if (logKey !== lastLoggedMessage && detail.item_description) {
          lastLoggedMessage = logKey
          const stageInfo = `[${detail.stage_index}/${detail.total_stages}]`
          if (detail.total_items > 0) {
            addLog(`${stageInfo} ${detail.current_stage_name}: ${detail.current_item}/${detail.total_items} - ${detail.item_description}`)
          } else {
            addLog(`${stageInfo} ${detail.current_stage_name}: ${detail.item_description}`)
          }
        }
      } else if (data.message) {
        // Pull the stage out of the message
        const match = data.message.match(/\[(\d+)\/(\d+)\]\s*([^:]+)/)
        if (match) {
          currentStage.value = match[3].trim()
        }
        // Log the message (without repeats)
        if (data.message !== lastLoggedMessage) {
          lastLoggedMessage = data.message
          addLog(data.message)
        }
      }
      
      // Check whether it has finished
      if (data.status === 'completed' || data.status === 'ready' || data.already_prepared) {
        addLog(t('log.prepareComplete'))
        stopPolling()
        stopProfilesPolling()
        await loadPreparedData()
      } else if (data.status === 'failed') {
        handlePrepareFailure(data.error)
      }
    }
  } catch (err) {
    console.warn('Failed to poll status:', err)
  }
}

const fetchProfilesRealtime = async () => {
  if (!props.simulationId) return
  
  try {
    const res = await getSimulationProfilesRealtime(props.simulationId)
    
    if (res.success && res.data) {
      const prevCount = profiles.value.length
      profiles.value = res.data.profiles || []
      // Only update when the API returns a valid value, so an existing valid value is not overwritten
      if (res.data.total_expected) {
        expectedTotal.value = res.data.total_expected
      }
      
      // Collect the entity types
      const types = new Set()
      profiles.value.forEach(p => {
        if (p.entity_type) types.add(p.entity_type)
      })
      entityTypes.value = Array.from(types)
      
      // Log profile generation progress (only when the count changes)
      const currentCount = profiles.value.length
      if (currentCount > 0 && currentCount !== lastLoggedProfileCount) {
        lastLoggedProfileCount = currentCount
        const total = expectedTotal.value || '?'
        const latestProfile = profiles.value[currentCount - 1]
        const profileName = latestProfile?.name || latestProfile?.username || `Agent_${currentCount}`
        if (currentCount === 1) {
          addLog(t('log.startGeneratingAgentProfiles'))
        }
        addLog(t('log.agentProfile', { current: currentCount, total: total, name: profileName, profession: latestProfile?.profession || t('step2.unknownProfession') }))

        // If every profile has been generated
        if (expectedTotal.value && currentCount >= expectedTotal.value) {
          addLog(t('log.allProfilesComplete', { count: currentCount }))
        }
      }
    }
  } catch (err) {
    console.warn('Failed to fetch profiles:', err)
  }
}

// Config polling
const startConfigPolling = () => {
  configTimer = setInterval(fetchConfigRealtime, 2000)
}

const stopConfigPolling = () => {
  if (configTimer) {
    clearInterval(configTimer)
    configTimer = null
  }
}

const fetchConfigRealtime = async () => {
  if (!props.simulationId) return
  
  try {
    const res = await getSimulationConfigRealtime(props.simulationId)
    
    if (res.success && res.data) {
      const data = res.data

      if (data.status === 'failed' || data.error) {
        handlePrepareFailure(data.error)
        return
      }
      
      // Log the config generation stage (without repeats)
      if (data.generation_stage && data.generation_stage !== lastLoggedConfigStage) {
        lastLoggedConfigStage = data.generation_stage
        if (data.generation_stage === 'generating_profiles') {
          addLog(t('log.generatingAgentProfileConfig'))
        } else if (data.generation_stage === 'generating_config') {
          addLog(t('log.generatingLLMConfig'))
        }
      }
      
      // If the config has been generated
      if (data.config_generated && data.config) {
        simulationConfig.value = data.config
        addLog(t('log.configComplete'))

        // Show a detailed config summary
        if (data.summary) {
          addLog(t('log.configSummaryAgents', { count: data.summary.total_agents }))
          addLog(t('log.configSummaryHours', { hours: data.summary.simulation_hours }))
          addLog(t('log.configSummaryPosts', { count: data.summary.initial_posts_count }))
          addLog(t('log.configSummaryTopics', { count: data.summary.hot_topics_count }))
          addLog(t('log.configSummaryPlatforms', { twitter: data.summary.has_twitter_config ? '✓' : '✗', reddit: data.summary.has_reddit_config ? '✓' : '✗' }))
        }
        
        // Show the time config details
        if (data.config.time_config) {
          const tc = data.config.time_config
          addLog(t('log.timeConfigDetail', { minutes: tc.minutes_per_round, rounds: Math.floor((tc.total_simulation_hours * 60) / tc.minutes_per_round) }))
        }
        
        // Show the event config
        if (data.config.event_config?.narrative_direction) {
          const narrative = data.config.event_config.narrative_direction
          addLog(t('log.narrativeDirection', { direction: narrative.length > 50 ? narrative.substring(0, 50) + '...' : narrative }))
        }
        
        stopConfigPolling()
        phase.value = 4
        addLog(t('log.envSetupComplete'))
        emit('update-status', 'completed')
      }
    }
  } catch (err) {
    console.warn('Failed to fetch config:', err)
  }
}

const loadPreparedData = async () => {
  phase.value = 2
  addLog(t('log.loadingExistingConfig'))

  // Fetch the profiles one last time
  await fetchProfilesRealtime()
  addLog(t('log.loadedAgentProfiles', { count: profiles.value.length }))

  // Fetch the config (using the real-time endpoint)
  try {
    const res = await getSimulationConfigRealtime(props.simulationId)
    if (res.success && res.data) {
      const configState = res.data

      if (configState.status === 'failed' || configState.error) {
        handlePrepareFailure(configState.error)
        return
      }

      if (configState.config_generated && configState.config) {
        simulationConfig.value = configState.config
        addLog(t('log.configLoadSuccess'))

        // Show a detailed config summary
        if (configState.summary) {
          addLog(t('log.configSummaryAgents', { count: configState.summary.total_agents }))
          addLog(t('log.configSummaryHours', { hours: configState.summary.simulation_hours }))
          addLog(t('log.configSummaryPostsAlt', { count: configState.summary.initial_posts_count }))
        }

        addLog(t('log.envSetupComplete'))
        phase.value = 4
        emit('update-status', 'completed')
      } else if (configState.is_generating) {
        addLog(t('log.configGenerating'))
        startConfigPolling()
      } else {
        handlePrepareFailure(t('log.configNotGenerating'))
      }
    }
  } catch (err) {
    handlePrepareFailure(t('log.loadConfigFailed', { error: err.message }))
  }
}

// Scroll log to bottom
const logContent = ref(null)
watch(() => props.systemLogs?.length, () => {
  nextTick(() => {
    if (logContent.value) {
      logContent.value.scrollTop = logContent.value.scrollHeight
    }
  })
})

onMounted(() => {
  loadPublicCap()
  // Start the preparation flow automatically
  if (props.simulationId) {
    addLog(t('log.step2Init'))
    startPrepareSimulation()
  }
})

onUnmounted(() => {
  stopPolling()
  stopProfilesPolling()
  stopConfigPolling()
})
</script>

<style scoped>
.env-setup-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--hm-paper);
  font-family: var(--hm-font-sans);
}

.scroll-container {
  flex: 1;
  overflow-y: auto;
  padding: var(--hm-space-6);
  display: flex;
  flex-direction: column;
  gap: var(--hm-space-4);
}

/* ---------------------------------------------------------- step cards */
.step-card {
  position: relative;
  background: var(--hm-surface);
  border: 1px solid var(--hm-line);
  border-radius: var(--hm-radius-lg);
  padding: var(--hm-space-5) var(--hm-space-6) var(--hm-space-6);
  transition: border-color var(--hm-duration) var(--hm-ease), box-shadow var(--hm-duration) var(--hm-ease);
}

.step-card.active {
  border-color: var(--hm-signal);
  box-shadow: 0 0 0 3px var(--hm-signal-soft);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--hm-space-3);
  margin-bottom: var(--hm-space-3);
}

.step-info {
  display: flex;
  align-items: baseline;
  gap: var(--hm-space-3);
  min-width: 0;
}

.step-num {
  font-family: var(--hm-font-mono);
  font-size: var(--hm-text-sm);
  font-weight: 500;
  color: var(--hm-ink-4);
  font-variant-numeric: tabular-nums;
}

.step-card.completed .step-num {
  color: var(--hm-ink);
}

.step-card.active .step-num {
  color: var(--hm-signal-ink);
}

.step-title {
  font-family: var(--hm-font-display);
  font-size: var(--hm-text-md);
  font-weight: 500;
  letter-spacing: -0.01em;
  color: var(--hm-ink);
}

.step-card:not(.active):not(.completed) .step-title {
  color: var(--hm-ink-3);
}

/* Status badges: same anatomy as .hm-pill */
.badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 22px;
  padding: 0 var(--hm-space-2);
  border-radius: var(--hm-radius-pill);
  font-size: var(--hm-text-2xs);
  font-weight: 500;
  font-family: var(--hm-font-mono);
  letter-spacing: 0.04em;
  text-transform: uppercase;
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}

.badge::before {
  content: "";
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
  flex-shrink: 0;
}

.badge.success { background: var(--hm-success-soft); color: var(--hm-success); }
.badge.success::before { background: var(--hm-success-dot); }
.badge.processing,
.badge.accent { background: var(--hm-signal-soft); color: var(--hm-signal-ink); }
.badge.processing::before,
.badge.accent::before { background: var(--hm-signal); animation: hm-pulse 1.4s var(--hm-ease) infinite; }
.badge.pending { background: var(--hm-surface-3); color: var(--hm-ink-3); }
.badge.pending::before { background: var(--hm-ink-5); }

.api-note {
  display: inline-block;
  font-family: var(--hm-font-mono);
  font-size: var(--hm-text-2xs);
  color: var(--hm-ink-4);
  margin-bottom: var(--hm-space-2);
}

.description {
  font-size: var(--hm-text-sm);
  color: var(--hm-ink-3);
  line-height: var(--hm-leading-normal);
  margin-bottom: var(--hm-space-4);
  max-width: 68ch;
}

/* Eyebrow labels used throughout the step */
.preview-title,
.config-block-title,
.timeline-label,
.box-label,
.modal-info-grid .info-label,
.modal-section .section-label {
  display: block;
  font-size: var(--hm-text-2xs);
  font-weight: 500;
  font-family: var(--hm-font-mono);
  letter-spacing: var(--hm-tracking-label);
  text-transform: uppercase;
  color: var(--hm-ink-4);
}

/* ------------------------------------------------------------- buttons */
.action-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--hm-space-2);
  height: 44px;
  padding: 0 var(--hm-space-5);
  border: 1px solid transparent;
  border-radius: var(--hm-radius-sm);
  font-size: var(--hm-text-base);
  font-weight: 600;
  white-space: nowrap;
  cursor: pointer;
  transition: background-color var(--hm-duration-fast) var(--hm-ease), border-color var(--hm-duration-fast) var(--hm-ease);
}

.action-btn.primary {
  background: var(--hm-signal);
  color: var(--hm-ink);
}

.action-btn.primary:hover:not(:disabled) {
  background: var(--hm-signal-hover);
}

.action-btn.secondary {
  background: var(--hm-surface);
  border-color: var(--hm-line-strong);
  color: var(--hm-ink);
}

.action-btn.secondary:hover:not(:disabled) {
  background: var(--hm-surface-2);
  border-color: var(--hm-ink-5);
}

.action-btn:disabled {
  background: var(--hm-surface-3);
  border-color: transparent;
  color: var(--hm-ink-5);
  cursor: not-allowed;
}

.action-group {
  display: flex;
  gap: var(--hm-space-3);
  margin-top: var(--hm-space-4);
}

.action-group.dual {
  display: grid;
  grid-template-columns: 1fr 1fr;
}

.action-group.dual .action-btn {
  width: 100%;
}

/* ----------------------------------------------------------- id table */
.info-card {
  margin-top: var(--hm-space-4);
  padding: var(--hm-space-1) var(--hm-space-4);
  background: var(--hm-surface-2);
  border: 1px solid var(--hm-line);
  border-radius: var(--hm-radius-md);
}

.info-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--hm-space-4);
  padding: var(--hm-space-2) 0;
  border-bottom: 1px solid var(--hm-line);
}

.info-row:last-child {
  border-bottom: none;
}

.info-card .info-label {
  font-size: var(--hm-text-xs);
  color: var(--hm-ink-4);
}

.info-card .info-value {
  font-size: var(--hm-text-sm);
  font-weight: 500;
  color: var(--hm-ink);
  text-align: right;
  word-break: break-all;
}

.info-card .info-value.mono {
  font-family: var(--hm-font-mono);
  font-size: var(--hm-text-xs);
}

/* --------------------------------------------------------------- stats */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  background: var(--hm-surface-2);
  border: 1px solid var(--hm-line);
  border-radius: var(--hm-radius-md);
}

.stat-card {
  display: flex;
  flex-direction: column;
  gap: var(--hm-space-1);
  padding: var(--hm-space-4) var(--hm-space-5);
}

.stat-card + .stat-card {
  border-left: 1px solid var(--hm-line);
}

.stat-value {
  font-family: var(--hm-font-display);
  font-size: var(--hm-text-2xl);
  font-weight: 500;
  line-height: 1.05;
  letter-spacing: var(--hm-tracking-display);
  font-variant-numeric: tabular-nums;
  color: var(--hm-ink);
}

.stat-label {
  font-size: var(--hm-text-2xs);
  font-weight: 500;
  font-family: var(--hm-font-mono);
  letter-spacing: var(--hm-tracking-label);
  text-transform: uppercase;
  color: var(--hm-ink-4);
}

/* ------------------------------------------------------ persona preview */
.profiles-preview {
  margin-top: var(--hm-space-5);
  padding-top: var(--hm-space-4);
  border-top: 1px solid var(--hm-line);
}

.preview-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--hm-space-3);
}

.profiles-list,
.agents-cards {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--hm-space-3);
  padding-right: var(--hm-space-1);
  overflow-y: auto;
}

.profiles-list {
  max-height: 320px;
}

.agents-cards {
  max-height: 400px;
}

.profiles-list::-webkit-scrollbar,
.agents-cards::-webkit-scrollbar {
  width: 4px;
}

.profiles-list::-webkit-scrollbar-thumb,
.agents-cards::-webkit-scrollbar-thumb {
  background: var(--hm-line-strong);
  border: none;
  border-radius: 2px;
}

.profile-card,
.agent-card {
  padding: var(--hm-space-4);
  background: var(--hm-surface);
  border: 1px solid var(--hm-line);
  border-radius: var(--hm-radius-md);
  transition: border-color var(--hm-duration-fast) var(--hm-ease), box-shadow var(--hm-duration-fast) var(--hm-ease);
}

.profile-card {
  cursor: pointer;
}

.profile-card:hover,
.agent-card:hover {
  border-color: var(--hm-ink-5);
  box-shadow: var(--hm-shadow-xs);
}

.profile-header {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 0 var(--hm-space-2);
  margin-bottom: 6px;
}

.profile-realname {
  font-size: var(--hm-text-base);
  font-weight: 600;
  color: var(--hm-ink);
}

.profile-username {
  font-family: var(--hm-font-mono);
  font-size: var(--hm-text-2xs);
  color: var(--hm-ink-4);
}

.profile-meta {
  margin-bottom: var(--hm-space-2);
}

.profile-profession {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  font-size: var(--hm-text-xs);
  font-weight: 500;
  line-height: 1.45;
  color: var(--hm-ink-2);
}

.modal-profession {
  display: block;
  font-size: var(--hm-text-sm);
  line-height: var(--hm-leading-normal);
  color: var(--hm-ink-3);
}

.agent-type {
  display: inline-block;
  padding: 2px var(--hm-space-2);
  background: var(--hm-surface-2);
  border: 1px solid var(--hm-line);
  border-radius: var(--hm-radius-xs);
  font-size: var(--hm-text-2xs);
  font-weight: 500;
  color: var(--hm-ink-2);
}

.profile-bio {
  margin: 0 0 var(--hm-space-3);
  font-size: var(--hm-text-xs);
  line-height: 1.55;
  color: var(--hm-ink-3);
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.profile-topics {
  display: flex;
  flex-wrap: wrap;
  gap: var(--hm-space-1);
}

.topic-tag,
.topic-item,
.hot-topic-tag {
  display: inline-flex;
  align-items: center;
  padding: 2px var(--hm-space-2);
  background: var(--hm-surface-2);
  border: 1px solid var(--hm-line);
  border-radius: var(--hm-radius-xs);
  font-size: var(--hm-text-2xs);
  color: var(--hm-ink-2);
}

.topic-more {
  padding: 2px var(--hm-space-1);
  font-size: var(--hm-text-2xs);
  color: var(--hm-ink-4);
}

/* -------------------------------------------------------- config detail */
.config-detail-panel {
  margin-top: var(--hm-space-4);
}

.config-block {
  margin-top: var(--hm-space-5);
  padding-top: var(--hm-space-4);
  border-top: 1px solid var(--hm-line);
}

.config-block:first-child {
  margin-top: 0;
  padding-top: 0;
  border-top: none;
}

.config-block-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--hm-space-3);
}

.config-block-badge {
  padding: 2px var(--hm-space-2);
  background: var(--hm-surface-3);
  border-radius: var(--hm-radius-pill);
  font-family: var(--hm-font-mono);
  font-size: var(--hm-text-2xs);
  color: var(--hm-ink-2);
}

.config-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--hm-space-2);
}

.config-item {
  display: flex;
  flex-direction: column;
  gap: var(--hm-space-1);
  padding: var(--hm-space-3);
  background: var(--hm-surface-2);
  border: 1px solid var(--hm-line);
  border-radius: var(--hm-radius-md);
}

.config-item-label {
  font-size: var(--hm-text-2xs);
  color: var(--hm-ink-4);
}

.config-item-value {
  font-family: var(--hm-font-display);
  font-size: var(--hm-text-lg);
  font-weight: 500;
  letter-spacing: -0.01em;
  font-variant-numeric: tabular-nums;
  color: var(--hm-ink);
}

.time-periods {
  display: flex;
  flex-direction: column;
  margin-top: var(--hm-space-3);
  border: 1px solid var(--hm-line);
  border-radius: var(--hm-radius-md);
  overflow: hidden;
}

.period-item {
  display: flex;
  align-items: center;
  gap: var(--hm-space-3);
  padding: var(--hm-space-2) var(--hm-space-3);
  background: var(--hm-surface);
}

.period-item + .period-item {
  border-top: 1px solid var(--hm-line);
}

.period-label {
  min-width: 96px;
  font-size: var(--hm-text-xs);
  font-weight: 500;
  color: var(--hm-ink-3);
}

.period-hours {
  flex: 1;
  font-family: var(--hm-font-mono);
  font-size: var(--hm-text-2xs);
  color: var(--hm-ink-2);
}

.period-multiplier {
  padding: 2px 6px;
  background: var(--hm-surface-3);
  border-radius: var(--hm-radius-xs);
  font-family: var(--hm-font-mono);
  font-size: var(--hm-text-2xs);
  font-weight: 600;
  color: var(--hm-ink);
}

/* Agent cards */
.agent-card-header {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  align-items: flex-start;
  gap: var(--hm-space-2);
  margin-bottom: var(--hm-space-3);
  padding-bottom: var(--hm-space-3);
  border-bottom: 1px solid var(--hm-line);
}

.agent-identity {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.agent-id {
  font-family: var(--hm-font-mono);
  font-size: 10px;
  color: var(--hm-ink-4);
}

.agent-name {
  font-size: var(--hm-text-base);
  font-weight: 600;
  color: var(--hm-ink);
}

.agent-tags {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: var(--hm-space-1);
}

.agent-stance {
  display: inline-flex;
  align-items: center;
  height: 20px;
  padding: 0 var(--hm-space-2);
  border-radius: var(--hm-radius-pill);
  font-size: 10px;
  font-weight: 500;
  font-family: var(--hm-font-mono);
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.stance-neutral { background: var(--hm-surface-3); color: var(--hm-ink-3); }
.stance-supportive { background: var(--hm-success-soft); color: var(--hm-success); }
.stance-opposing { background: var(--hm-danger-soft); color: var(--hm-danger); }
.stance-observer { background: transparent; box-shadow: inset 0 0 0 1px var(--hm-line-strong); color: var(--hm-ink-3); }

.agent-timeline {
  margin-bottom: var(--hm-space-3);
}

.timeline-label {
  margin-bottom: 6px;
}

.mini-timeline {
  display: flex;
  gap: 2px;
  height: 14px;
}

.timeline-hour {
  flex: 1;
  background: var(--hm-surface-3);
  border-radius: 1px;
}

.timeline-hour.active {
  background: var(--hm-ink);
}

.timeline-marks {
  display: flex;
  justify-content: space-between;
  margin-top: var(--hm-space-1);
  font-family: var(--hm-font-mono);
  font-size: 10px;
  color: var(--hm-ink-4);
}

.agent-params {
  display: flex;
  flex-direction: column;
  gap: var(--hm-space-3);
}

.param-group {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--hm-space-2);
}

.param-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.param-item .param-label {
  font-size: 10px;
  color: var(--hm-ink-4);
}

.param-item .param-value {
  font-family: var(--hm-font-mono);
  font-size: var(--hm-text-xs);
  font-weight: 600;
  color: var(--hm-ink);
}

.param-value.with-bar {
  display: flex;
  align-items: center;
  gap: 6px;
}

.mini-bar {
  height: 4px;
  min-width: 4px;
  max-width: 40px;
  background: var(--hm-ink);
  border-radius: 2px;
}

.param-value.positive { color: var(--hm-success); }
.param-value.negative { color: var(--hm-danger); }
.param-value.neutral { color: var(--hm-ink-3); }
.param-value.highlight { color: var(--hm-ink); font-weight: 700; }

/* Recommendation algorithm */
.platforms-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--hm-space-3);
}

.platform-card {
  padding: var(--hm-space-4);
  background: var(--hm-surface-2);
  border: 1px solid var(--hm-line);
  border-radius: var(--hm-radius-md);
}

.platform-card-header {
  margin-bottom: var(--hm-space-3);
  padding-bottom: var(--hm-space-2);
  border-bottom: 1px solid var(--hm-line);
}

.platform-name {
  font-size: var(--hm-text-sm);
  font-weight: 600;
  color: var(--hm-ink);
}

.platform-params {
  display: flex;
  flex-direction: column;
  gap: var(--hm-space-2);
}

.param-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.param-row .param-label {
  font-size: var(--hm-text-xs);
  color: var(--hm-ink-3);
}

.param-row .param-value {
  font-family: var(--hm-font-mono);
  font-size: var(--hm-text-xs);
  font-weight: 600;
  color: var(--hm-ink);
  font-variant-numeric: tabular-nums;
}

/* LLM reasoning */
.reasoning-content {
  display: flex;
  flex-direction: column;
  gap: var(--hm-space-2);
}

.reasoning-item {
  padding: var(--hm-space-3) var(--hm-space-4);
  background: var(--hm-surface-2);
  border-left: 2px solid var(--hm-line-strong);
  border-radius: 0 var(--hm-radius-sm) var(--hm-radius-sm) 0;
}

.reasoning-text {
  margin: 0;
  font-size: var(--hm-text-sm);
  line-height: var(--hm-leading-relaxed);
  color: var(--hm-ink-3);
}

/* ------------------------------------------------- initial activation */
.orchestration-content {
  display: flex;
  flex-direction: column;
  gap: var(--hm-space-5);
  margin-top: var(--hm-space-4);
}

.box-label {
  margin-bottom: var(--hm-space-3);
}

.narrative-box {
  padding: var(--hm-space-4) var(--hm-space-5);
  background: var(--hm-surface-2);
  border: 1px solid var(--hm-line);
  border-radius: var(--hm-radius-md);
}

.narrative-box .box-label {
  display: flex;
  align-items: center;
  gap: var(--hm-space-2);
}

.special-icon {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
}

.narrative-text {
  margin: 0;
  font-size: var(--hm-text-base);
  line-height: var(--hm-leading-relaxed);
  color: var(--hm-ink-2);
}

.hot-topics-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.hot-topic-tag {
  font-size: var(--hm-text-xs);
  padding: 3px var(--hm-space-2);
}

.hot-topic-more {
  padding: 4px 6px;
  font-size: var(--hm-text-2xs);
  color: var(--hm-ink-4);
}

.initial-posts-section {
  padding-top: var(--hm-space-4);
  border-top: 1px solid var(--hm-line);
}

.posts-timeline {
  display: flex;
  flex-direction: column;
  gap: var(--hm-space-3);
  margin-top: var(--hm-space-3);
  padding-left: var(--hm-space-2);
  border-left: 1px solid var(--hm-line-strong);
}

.timeline-item {
  position: relative;
  padding-left: var(--hm-space-4);
}

.timeline-marker {
  position: absolute;
  left: -12px;
  top: 16px;
  width: 7px;
  height: 7px;
  background: var(--hm-surface);
  border: 1.5px solid var(--hm-ink-4);
  border-radius: 50%;
}

.timeline-content {
  padding: var(--hm-space-3);
  background: var(--hm-surface);
  border: 1px solid var(--hm-line);
  border-radius: var(--hm-radius-md);
}

.post-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--hm-space-2);
  margin-bottom: 6px;
}

.post-role {
  font-size: var(--hm-text-2xs);
  font-weight: 500;
  font-family: var(--hm-font-mono);
  letter-spacing: var(--hm-tracking-label);
  text-transform: uppercase;
  color: var(--hm-ink-2);
}

.post-agent-info {
  display: flex;
  align-items: center;
  gap: 6px;
}

.post-id,
.post-username {
  font-family: var(--hm-font-mono);
  font-size: 10px;
  line-height: 1;
  color: var(--hm-ink-4);
}

.post-text {
  margin: 0;
  font-size: var(--hm-text-sm);
  line-height: var(--hm-leading-normal);
  color: var(--hm-ink-2);
}

/* ------------------------------------------------------ rounds config */
.rounds-config-section {
  margin: var(--hm-space-6) 0;
  padding-top: var(--hm-space-5);
  border-top: 1px solid var(--hm-line);
}

.rounds-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: var(--hm-space-4);
  margin-bottom: var(--hm-space-4);
}

.header-left {
  display: flex;
  flex-direction: column;
  gap: var(--hm-space-1);
}

.rounds-header .section-title {
  font-size: var(--hm-text-base);
  font-weight: 600;
  color: var(--hm-ink);
}

.section-desc {
  font-size: var(--hm-text-xs);
  line-height: var(--hm-leading-normal);
  color: var(--hm-ink-4);
}

.desc-highlight {
  margin: 0 2px;
  padding: 1px 6px;
  background: var(--hm-surface-3);
  border-radius: var(--hm-radius-xs);
  font-family: var(--hm-font-mono);
  font-weight: 600;
  color: var(--hm-ink);
}

.switch-control {
  display: flex;
  align-items: center;
  gap: var(--hm-space-2);
  flex-shrink: 0;
  height: 30px;
  padding: 0 var(--hm-space-3) 0 6px;
  border: 1px solid var(--hm-line-strong);
  border-radius: var(--hm-radius-pill);
  cursor: pointer;
  transition: background-color var(--hm-duration-fast) var(--hm-ease);
}

.switch-control:hover {
  background: var(--hm-surface-2);
}

.switch-control input {
  display: none;
}

.switch-track {
  position: relative;
  width: 32px;
  height: 18px;
  background: var(--hm-line-strong);
  border-radius: var(--hm-radius-pill);
  transition: background-color var(--hm-duration) var(--hm-ease);
}

.switch-track::after {
  content: "";
  position: absolute;
  left: 2px;
  top: 2px;
  width: 14px;
  height: 14px;
  background: var(--hm-surface);
  border-radius: 50%;
  box-shadow: var(--hm-shadow-xs);
  transition: transform var(--hm-duration) var(--hm-ease);
}

.switch-control input:checked + .switch-track {
  background: var(--hm-ink);
}

.switch-control input:checked + .switch-track::after {
  transform: translateX(14px);
}

.switch-label {
  font-size: var(--hm-text-xs);
  font-weight: 600;
  color: var(--hm-ink-3);
}

.switch-control input:checked ~ .switch-label {
  color: var(--hm-ink);
}

.rounds-content {
  animation: fadeIn var(--hm-duration) var(--hm-ease);
}

.slider-display {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  margin-bottom: var(--hm-space-4);
}

.slider-main-value,
.auto-value {
  display: flex;
  align-items: baseline;
  gap: 6px;
}

.val-num {
  font-family: var(--hm-font-display);
  font-size: var(--hm-text-2xl);
  font-weight: 500;
  line-height: 1;
  letter-spacing: var(--hm-tracking-display);
  font-variant-numeric: tabular-nums;
  color: var(--hm-ink);
}

.val-unit {
  font-size: var(--hm-text-xs);
  font-weight: 500;
  color: var(--hm-ink-4);
}

.slider-meta-info,
.duration-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 3px var(--hm-space-2);
  background: var(--hm-surface-2);
  border: 1px solid var(--hm-line);
  border-radius: var(--hm-radius-xs);
  font-family: var(--hm-font-mono);
  font-size: var(--hm-text-2xs);
  color: var(--hm-ink-3);
}

.range-wrapper {
  position: relative;
  padding: 0 2px;
}

.minimal-slider {
  -webkit-appearance: none;
  appearance: none;
  width: 100%;
  height: 4px;
  background: var(--hm-surface-3);
  background-image: linear-gradient(var(--hm-ink), var(--hm-ink));
  background-size: var(--percent, 0%) 100%;
  background-repeat: no-repeat;
  border-radius: 2px;
  outline: none;
  cursor: pointer;
}

.minimal-slider:focus-visible {
  outline: 2px solid var(--hm-ink);
  outline-offset: 6px;
}

.minimal-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 16px;
  height: 16px;
  margin-top: -6px;
  background: var(--hm-surface);
  border: 2px solid var(--hm-ink);
  border-radius: 50%;
  box-shadow: var(--hm-shadow-xs);
  cursor: pointer;
}

.minimal-slider::-webkit-slider-runnable-track {
  height: 4px;
  border-radius: 2px;
}

.range-marks {
  position: relative;
  display: flex;
  justify-content: space-between;
  margin-top: var(--hm-space-2);
  font-family: var(--hm-font-mono);
  font-size: 10px;
  color: var(--hm-ink-4);
}

.mark-recommend {
  position: relative;
  cursor: pointer;
  transition: color var(--hm-duration-fast) var(--hm-ease);
}

.mark-recommend:hover,
.mark-recommend.active {
  color: var(--hm-ink);
}

.mark-recommend.active {
  font-weight: 600;
}

.mark-recommend::after {
  content: "";
  position: absolute;
  top: -12px;
  left: 50%;
  transform: translateX(-50%);
  width: 1px;
  height: 4px;
  background: var(--hm-line-strong);
}

.auto-info-card {
  display: flex;
  align-items: center;
  gap: var(--hm-space-6);
  padding: var(--hm-space-4) var(--hm-space-5);
  background: var(--hm-surface-2);
  border: 1px solid var(--hm-line);
  border-radius: var(--hm-radius-md);
}

.auto-value {
  padding-right: var(--hm-space-6);
  border-right: 1px solid var(--hm-line);
}

.auto-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: var(--hm-space-2);
}

.auto-meta-row {
  display: flex;
  align-items: center;
}

.auto-desc {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.auto-desc p {
  margin: 0;
  font-size: var(--hm-text-sm);
  line-height: var(--hm-leading-normal);
  color: var(--hm-ink-3);
}

.highlight-tip {
  margin-top: var(--hm-space-1) !important;
  font-size: var(--hm-text-xs) !important;
  font-weight: 500;
  color: var(--hm-ink) !important;
  text-decoration: underline;
  text-decoration-color: var(--hm-line-strong);
  text-underline-offset: 3px;
  cursor: pointer;
}

.highlight-tip:hover {
  text-decoration-color: var(--hm-ink);
}

/* ------------------------------------------------------- persona modal */
.profile-modal-overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--hm-space-6);
  background: var(--hm-overlay);
  backdrop-filter: blur(2px);
}

.profile-modal {
  display: flex;
  flex-direction: column;
  width: 100%;
  max-width: 600px;
  max-height: 85vh;
  overflow: hidden;
  background: var(--hm-surface);
  border-radius: var(--hm-radius-lg);
  box-shadow: var(--hm-shadow-lg);
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: var(--hm-space-4);
  padding: var(--hm-space-5) var(--hm-space-4) var(--hm-space-5) var(--hm-space-6);
  border-bottom: 1px solid var(--hm-line);
}

.modal-header-info {
  flex: 1;
  min-width: 0;
}

.modal-name-row {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 0 var(--hm-space-2);
  margin-bottom: var(--hm-space-2);
}

.modal-realname {
  font-family: var(--hm-font-display);
  font-size: var(--hm-text-lg);
  font-weight: 500;
  letter-spacing: -0.01em;
  color: var(--hm-ink);
}

.modal-username {
  font-family: var(--hm-font-mono);
  font-size: var(--hm-text-xs);
  color: var(--hm-ink-4);
}

.close-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  width: 32px;
  height: 32px;
  padding: 0;
  border: none;
  border-radius: var(--hm-radius-sm);
  background: transparent;
  color: var(--hm-ink-4);
  cursor: pointer;
  transition: background-color var(--hm-duration-fast) var(--hm-ease), color var(--hm-duration-fast) var(--hm-ease);
}

.close-btn:hover {
  background: var(--hm-surface-3);
  color: var(--hm-ink);
}

.modal-body {
  flex: 1;
  overflow-y: auto;
  padding: var(--hm-space-6);
}

.modal-info-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--hm-space-5) var(--hm-space-4);
  margin-bottom: var(--hm-space-8);
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: var(--hm-space-1);
}

.modal-info-grid .info-value {
  font-size: var(--hm-text-md);
  font-weight: 600;
  color: var(--hm-ink);
}

.modal-info-grid .info-value.mbti {
  font-family: var(--hm-font-mono);
  letter-spacing: 0.04em;
}

.modal-section {
  margin-bottom: var(--hm-space-6);
}

.modal-section .section-label {
  margin-bottom: var(--hm-space-3);
}

.section-bio {
  margin: 0;
  padding: var(--hm-space-3) var(--hm-space-4);
  background: var(--hm-surface-2);
  border-left: 2px solid var(--hm-ink);
  border-radius: 0 var(--hm-radius-sm) var(--hm-radius-sm) 0;
  font-size: var(--hm-text-base);
  line-height: var(--hm-leading-relaxed);
  color: var(--hm-ink-2);
}

.topics-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.topic-item {
  font-size: var(--hm-text-xs);
  padding: 3px var(--hm-space-2);
}

.persona-dimensions {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--hm-space-2);
  margin-bottom: var(--hm-space-4);
}

.dimension-card {
  padding: var(--hm-space-3);
  background: var(--hm-surface-2);
  border: 1px solid var(--hm-line);
  border-radius: var(--hm-radius-md);
}

.dim-title {
  display: block;
  margin-bottom: 2px;
  font-size: var(--hm-text-xs);
  font-weight: 600;
  color: var(--hm-ink);
}

.dim-desc {
  display: block;
  font-size: var(--hm-text-2xs);
  line-height: 1.4;
  color: var(--hm-ink-4);
}

.persona-content {
  padding: 0;
}

.section-persona {
  margin: 0;
  font-size: var(--hm-text-sm);
  line-height: 1.75;
  color: var(--hm-ink-2);
}

/* ------------------------------------------------------ live log console */
.system-logs {
  flex-shrink: 0;
  padding: var(--hm-space-3) var(--hm-space-5) var(--hm-space-4);
  background: var(--hm-console-bg);
  border-top: 1px solid var(--hm-console-line);
  color: var(--hm-console-text);
  font-family: var(--hm-font-mono);
}

.log-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--hm-space-3);
  padding-bottom: var(--hm-space-2);
  margin-bottom: var(--hm-space-2);
  border-bottom: 1px solid var(--hm-console-line);
}

.log-title {
  display: inline-flex;
  align-items: center;
  gap: var(--hm-space-2);
  
  font-size: var(--hm-text-2xs);
  font-weight: 500;
  font-family: var(--hm-font-mono);
  letter-spacing: var(--hm-tracking-label);
  text-transform: uppercase;
  color: var(--hm-console-muted);
}

.log-title::before {
  content: "";
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--hm-on-ink);
}

.log-id {
  font-size: var(--hm-text-2xs);
  color: var(--hm-console-muted);
}

.log-content {
  display: flex;
  flex-direction: column;
  gap: 2px;
  height: 84px;
  overflow-y: auto;
  padding-right: var(--hm-space-1);
}

.log-content::-webkit-scrollbar {
  width: 4px;
}

.log-content::-webkit-scrollbar-thumb {
  background: var(--hm-console-line);
  border: none;
  border-radius: 2px;
}

.log-line {
  display: flex;
  gap: var(--hm-space-3);
  font-size: var(--hm-text-xs);
  line-height: 1.6;
}

.log-time {
  min-width: 84px;
  color: var(--hm-console-muted);
  font-variant-numeric: tabular-nums;
}

.log-msg {
  color: var(--hm-console-text);
  word-break: break-word;
}

/* Spinner */
.spinner-sm {
  width: 16px;
  height: 16px;
  border: 2px solid var(--hm-line-strong);
  border-top-color: var(--hm-ink);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

@keyframes hm-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.35; }
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(4px); }
  to { opacity: 1; transform: translateY(0); }
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity var(--hm-duration) var(--hm-ease);
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* Modal transition */
.modal-enter-active,
.modal-leave-active {
  transition: opacity var(--hm-duration) var(--hm-ease);
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.modal-enter-active .profile-modal,
.modal-leave-active .profile-modal {
  transition: transform var(--hm-duration) var(--hm-ease), opacity var(--hm-duration) var(--hm-ease);
}

.modal-enter-from .profile-modal,
.modal-leave-to .profile-modal {
  transform: translateY(8px) scale(0.98);
  opacity: 0;
}

@media (max-width: 900px) {
  .config-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .profiles-list,
  .agents-cards,
  .platforms-grid {
    grid-template-columns: 1fr;
  }
}

/* Hivemind: cast tree shown while agents are spun up */
.cast-embed { margin: var(--hm-space-4) 0; }
</style>
