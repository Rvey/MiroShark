<template>
  <div class="strategy-panel">
    <div class="main-layout">
      <div class="content-pane">
        <div v-if="strategyOutline" class="strategy-content">
          <div class="strategy-header">
            <div class="header-meta">
              <span class="strategy-tag">Marketing Strategy</span>
              <button class="copy-id" @click="copyStrategyId">ID: {{ strategyId }}</button>
            </div>
            <h1 class="strategy-title">{{ strategyOutline.title }}</h1>
            <p class="strategy-summary">{{ strategyOutline.summary }}</p>
          </div>

          <section v-if="problems.length > 0" class="problem-section">
            <div class="section-title-row">
              <h2>Priority Problems</h2>
              <span>{{ problems.length }} items</span>
            </div>
            <div class="problem-grid">
              <article v-for="(problem, index) in problems" :key="`${problem.problem}-${index}`" class="problem-card">
                <div class="problem-head">
                  <span class="problem-index">{{ String(index + 1).padStart(2, '0') }}</span>
                  <span class="problem-priority" :class="`priority-${problem.priority || 'medium'}`">{{ problem.priority || 'medium' }}</span>
                </div>
                <h3>{{ problem.problem }}</h3>
                <p v-if="problem.evidence"><strong>Evidence:</strong> {{ problem.evidence }}</p>
                <p v-if="problem.root_cause"><strong>Root Cause:</strong> {{ problem.root_cause }}</p>
                <ul v-if="problem.recommended_actions?.length">
                  <li v-for="(action, actionIndex) in problem.recommended_actions" :key="`${problem.problem}-${actionIndex}`">{{ action }}</li>
                </ul>
                <p v-if="problem.solution"><strong>Solution:</strong> {{ problem.solution }}</p>
              </article>
            </div>
          </section>

          <section class="generated-sections">
            <div v-for="(section, index) in strategyOutline.sections" :key="section.title" class="section-card">
              <div class="section-card-header">
                <span class="section-number">{{ String(index + 1).padStart(2, '0') }}</span>
                <h3>{{ section.title }}</h3>
                <span v-if="generatedSections[index + 1]" class="section-state done">Done</span>
                <span v-else-if="currentSectionIndex === index + 1" class="section-state active">Working</span>
                <span v-else class="section-state pending">Pending</span>
              </div>
              <div v-if="generatedSections[index + 1]" class="section-body" v-html="renderMarkdown(generatedSections[index + 1])"></div>
              <div v-else-if="currentSectionIndex === index + 1" class="section-loading">Generating section content...</div>
            </div>
          </section>

          <div v-if="isComplete" class="completion-actions">
            <button class="report-link-btn" @click="goToSourceReport">Open Source Report</button>
          </div>
        </div>

        <div v-else class="waiting-state">
          <div class="waiting-ring"></div>
          <span>Waiting for marketing strategy agent...</span>
        </div>
      </div>

      <div class="timeline-pane">
        <div class="timeline-overview">
          <div class="metric">
            <span class="metric-label">Problems</span>
            <span class="metric-value">{{ problems.length }}</span>
          </div>
          <div class="metric">
            <span class="metric-label">Sections</span>
            <span class="metric-value">{{ completedSections }}/{{ totalSections }}</span>
          </div>
          <div class="metric">
            <span class="metric-label">Tools</span>
            <span class="metric-value">{{ totalToolCalls }}</span>
          </div>
          <div class="metric">
            <span class="metric-label">Status</span>
            <span class="metric-value">{{ statusText }}</span>
          </div>
        </div>

        <div class="timeline-list">
          <div v-for="(log, index) in agentLogs" :key="`${log.timestamp}-${index}`" class="timeline-item">
            <div class="timeline-item-header">
              <span class="timeline-label">{{ getActionLabel(log.action) }}</span>
              <span class="timeline-time">{{ formatTime(log.timestamp) }}</span>
            </div>
            <div class="timeline-item-body">
              <template v-if="log.action === 'report_start'">
                <p>Started from report {{ log.details?.report_id }}</p>
              </template>
              <template v-else-if="log.action === 'planning_complete'">
                <p>{{ log.details?.message }}</p>
                <p>{{ log.details?.problems?.length || 0 }} problems prioritized across {{ log.details?.outline?.sections?.length || 0 }} sections.</p>
              </template>
              <template v-else-if="log.action === 'tool_call'">
                <p><strong>{{ log.details?.tool_name }}</strong></p>
                <pre v-if="log.details?.parameters">{{ formatParams(log.details.parameters) }}</pre>
              </template>
              <template v-else-if="log.action === 'tool_result'">
                <p><strong>{{ log.details?.tool_name }}</strong></p>
                <pre>{{ truncateText(log.details?.result, 320) }}</pre>
              </template>
              <template v-else-if="log.action === 'section_complete'">
                <p>{{ log.section_title }} completed</p>
              </template>
              <template v-else>
                <p>{{ log.details?.message || 'Processing...' }}</p>
              </template>
            </div>
          </div>

          <div v-if="agentLogs.length === 0 && !isComplete" class="timeline-empty">Waiting for agent activity...</div>
        </div>
      </div>
    </div>

    <div class="console-logs" :class="{ collapsed: consoleCollapsed }">
      <div class="console-header" @click="consoleCollapsed = !consoleCollapsed">
        <span>CONSOLE OUTPUT <span>{{ consoleCollapsed ? '▲' : '▼' }}</span></span>
        <span>{{ strategyId || 'NO_STRATEGY' }}</span>
      </div>
      <div v-show="!consoleCollapsed" ref="logContent" class="console-body">
        <div v-for="(log, index) in consoleLogs" :key="index" class="console-line">{{ log }}</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
  getMarketingStrategyAgentLog,
  getMarketingStrategyConsoleLog,
  getMarketingStrategy,
} from '../api/marketingStrategy'

const router = useRouter()

const props = defineProps({
  strategyId: String,
  simulationId: String,
  systemLogs: Array
})

const emit = defineEmits(['add-log', 'update-status'])

const consoleCollapsed = ref(false)
const agentLogs = ref([])
const consoleLogs = ref([])
const agentLogLine = ref(0)
const consoleLogLine = ref(0)
const strategyOutline = ref(null)
const problems = ref([])
const currentSectionIndex = ref(null)
const generatedSections = ref({})
const isComplete = ref(false)
const sourceReportId = ref(null)
const logContent = ref(null)

const statusText = computed(() => {
  if (isComplete.value) return 'Completed'
  if (agentLogs.value.length > 0) return 'Generating'
  return 'Waiting'
})

const totalSections = computed(() => strategyOutline.value?.sections?.length || 0)
const completedSections = computed(() => Object.keys(generatedSections.value).length)
const totalToolCalls = computed(() => agentLogs.value.filter(log => log.action === 'tool_call').length)

const addLog = (msg) => emit('add-log', msg)

const copyStrategyId = () => {
  if (props.strategyId) {
    navigator.clipboard.writeText(props.strategyId)
  }
}

const goToSourceReport = () => {
  if (sourceReportId.value) {
    router.push({ name: 'Report', params: { reportId: sourceReportId.value } })
  }
}

const formatTime = (timestamp) => {
  if (!timestamp) return ''
  try {
    return new Date(timestamp).toLocaleTimeString('en-US', {
      hour12: false,
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    })
  } catch {
    return ''
  }
}

const getActionLabel = (action) => {
  const labels = {
    report_start: 'Strategy Started',
    planning_start: 'Planning',
    planning_complete: 'Plan Complete',
    section_start: 'Section Start',
    section_complete: 'Section Done',
    tool_call: 'Tool Call',
    tool_result: 'Tool Result',
    llm_response: 'LLM Response',
    report_complete: 'Complete'
  }
  return labels[action] || action
}

const formatParams = (params) => {
  try {
    return JSON.stringify(params, null, 2)
  } catch {
    return String(params || '')
  }
}

const truncateText = (text, maxLen) => {
  if (!text) return ''
  return text.length <= maxLen ? text : `${text.slice(0, maxLen)}...`
}

const renderMarkdown = (content) => {
  if (!content) return ''

  let html = content.replace(/^##\s+.+\n+/, '')
  html = html.replace(/```([\s\S]*?)```/g, '<pre class="md-code"><code>$1</code></pre>')
  html = html.replace(/^> (.+)$/gm, '<blockquote>$1</blockquote>')
  html = html.replace(/^### (.+)$/gm, '<h4>$1</h4>')
  html = html.replace(/^## (.+)$/gm, '<h3>$1</h3>')
  html = html.replace(/^# (.+)$/gm, '<h2>$1</h2>')
  html = html.replace(/^\- (.+)$/gm, '<li>$1</li>')
  html = html.replace(/(<li>.*?<\/li>\s*)+/gs, '<ul>$&</ul>')
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  html = html.replace(/\n\n/g, '</p><p>')
  html = html.replace(/\n/g, '<br>')
  html = `<p>${html}</p>`
  html = html.replace(/<p>(<h[2-4]|<ul|<blockquote|<pre)/g, '$1')
  html = html.replace(/(<\/h[2-4]>|<\/ul>|<\/blockquote>|<\/pre>)<\/p>/g, '$1')
  html = html.replace(/<p><\/p>/g, '')
  return html
}

let agentTimer = null
let consoleTimer = null

const loadStrategyMeta = async () => {
  if (!props.strategyId) return
  try {
    const res = await getMarketingStrategy(props.strategyId)
    if (res.success && res.data) {
      sourceReportId.value = res.data.report_id
      if (res.data.outline && !strategyOutline.value) {
        strategyOutline.value = res.data.outline
      }
      if (Array.isArray(res.data.problems) && problems.value.length === 0) {
        problems.value = res.data.problems
      }
    }
  } catch (error) {
    console.warn('Failed to load strategy metadata:', error)
  }
}

const fetchAgentLog = async () => {
  if (!props.strategyId) return
  try {
    const res = await getMarketingStrategyAgentLog(props.strategyId, agentLogLine.value)
    if (!res.success || !res.data) return

    const newLogs = res.data.logs || []
    if (newLogs.length === 0) return

    newLogs.forEach(log => {
      agentLogs.value.push(log)
      if (log.action === 'report_start') {
        sourceReportId.value = log.details?.report_id || sourceReportId.value
      }
      if (log.action === 'planning_complete') {
        strategyOutline.value = log.details?.outline || strategyOutline.value
        problems.value = log.details?.problems || problems.value
      }
      if (log.action === 'section_start') {
        currentSectionIndex.value = log.section_index
      }
      if (log.action === 'section_complete' && log.details?.content) {
        generatedSections.value[log.section_index] = log.details.content
        currentSectionIndex.value = null
      }
      if (log.action === 'report_complete') {
        isComplete.value = true
        currentSectionIndex.value = null
        emit('update-status', 'completed')
        stopPolling()
      }
    })

    agentLogLine.value = res.data.from_line + newLogs.length
  } catch (error) {
    console.warn('Failed to fetch marketing strategy agent log:', error)
  }
}

const fetchConsoleLog = async () => {
  if (!props.strategyId) return
  try {
    const res = await getMarketingStrategyConsoleLog(props.strategyId, consoleLogLine.value)
    if (!res.success || !res.data) return

    const newLogs = res.data.logs || []
    if (newLogs.length === 0) return

    consoleLogs.value.push(...newLogs)
    consoleLogLine.value = res.data.from_line + newLogs.length

    nextTick(() => {
      if (logContent.value) {
        logContent.value.scrollTop = logContent.value.scrollHeight
      }
    })
  } catch (error) {
    console.warn('Failed to fetch marketing strategy console log:', error)
  }
}

const startPolling = () => {
  if (agentTimer || consoleTimer) return
  fetchAgentLog()
  fetchConsoleLog()
  agentTimer = setInterval(fetchAgentLog, 2000)
  consoleTimer = setInterval(fetchConsoleLog, 1500)
}

const stopPolling = () => {
  if (agentTimer) {
    clearInterval(agentTimer)
    agentTimer = null
  }
  if (consoleTimer) {
    clearInterval(consoleTimer)
    consoleTimer = null
  }
}

onMounted(() => {
  if (props.strategyId) {
    addLog(`Marketing Strategy Agent initialized: ${props.strategyId}`)
    loadStrategyMeta()
    startPolling()
  }
})

onUnmounted(() => {
  stopPolling()
})

watch(() => props.strategyId, (newId) => {
  if (!newId) return
  agentLogs.value = []
  consoleLogs.value = []
  agentLogLine.value = 0
  consoleLogLine.value = 0
  strategyOutline.value = null
  problems.value = []
  currentSectionIndex.value = null
  generatedSections.value = {}
  isComplete.value = false
  sourceReportId.value = null
  stopPolling()
  loadStrategyMeta()
  startPolling()
}, { immediate: false })
</script>

<style scoped>
.strategy-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #f5f5f5;
  font-family: var(--font-mono);
}

.main-layout {
  flex: 1;
  display: grid;
  grid-template-columns: minmax(0, 1.4fr) minmax(320px, 0.8fr);
  min-height: 0;
}

.content-pane,
.timeline-pane {
  overflow: auto;
}

.content-pane {
  padding: 24px;
}

.timeline-pane {
  border-left: 2px solid rgba(10,10,10,0.08);
  background: #ffffff;
  padding: 20px;
}

.strategy-header {
  padding: 24px;
  background: #ffffff;
  border: 1px solid rgba(10,10,10,0.08);
  margin-bottom: 20px;
}

.header-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.strategy-tag {
  font-size: 11px;
  letter-spacing: 2px;
  text-transform: uppercase;
  color: #FF6B1A;
  font-weight: 700;
}

.copy-id {
  border: none;
  background: transparent;
  font-family: var(--font-mono);
  font-size: 11px;
  color: rgba(10,10,10,0.56);
  cursor: pointer;
}

.strategy-title {
  margin: 0;
  font-size: 30px;
  line-height: 1.15;
  color: #0A0A0A;
}

.strategy-summary {
  margin: 12px 0 0;
  color: rgba(10,10,10,0.7);
  font-size: 14px;
  line-height: 1.6;
}

.problem-section,
.generated-sections {
  margin-top: 20px;
}

.section-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}

.section-title-row h2 {
  margin: 0;
  font-size: 16px;
  letter-spacing: 1px;
  text-transform: uppercase;
}

.problem-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 14px;
}

.problem-card,
.section-card {
  background: #ffffff;
  border: 1px solid rgba(10,10,10,0.08);
  padding: 16px;
}

.problem-head,
.section-card-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
}

.problem-head {
  justify-content: space-between;
}

.problem-index,
.section-number {
  font-size: 11px;
  letter-spacing: 2px;
  color: rgba(10,10,10,0.5);
}

.problem-priority,
.section-state {
  font-size: 10px;
  letter-spacing: 2px;
  text-transform: uppercase;
  padding: 4px 8px;
  border-radius: 999px;
}

.priority-high,
.section-state.active {
  background: rgba(255,107,26,0.12);
  color: #C24E00;
}

.priority-medium,
.section-state.pending {
  background: rgba(10,10,10,0.08);
  color: rgba(10,10,10,0.6);
}

.priority-low,
.section-state.done {
  background: rgba(67,193,101,0.14);
  color: #257A42;
}

.problem-card h3,
.section-card h3 {
  margin: 0 0 10px;
  font-size: 18px;
  line-height: 1.35;
}

.problem-card p,
.problem-card li,
.section-body :deep(p),
.section-body :deep(li) {
  font-size: 13px;
  line-height: 1.65;
  color: rgba(10,10,10,0.78);
}

.problem-card ul {
  margin: 10px 0;
  padding-left: 18px;
}

.section-card {
  margin-bottom: 12px;
}

.section-card-header h3 {
  flex: 1;
  margin: 0;
  font-size: 17px;
}

.section-body :deep(blockquote) {
  border-left: 3px solid #FF6B1A;
  margin: 14px 0;
  padding-left: 12px;
  color: rgba(10,10,10,0.72);
}

.section-body :deep(pre) {
  padding: 12px;
  background: #0A0A0A;
  color: #FAFAFA;
  overflow: auto;
}

.section-loading,
.timeline-empty,
.waiting-state {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 120px;
  color: rgba(10,10,10,0.48);
  letter-spacing: 1px;
}

.waiting-state {
  flex-direction: column;
  gap: 14px;
  min-height: 320px;
}

.waiting-ring {
  width: 42px;
  height: 42px;
  border-radius: 50%;
  border: 3px solid rgba(255,107,26,0.2);
  border-top-color: #FF6B1A;
  animation: spin 1s linear infinite;
}

.timeline-overview {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 18px;
}

.metric {
  background: #F5F5F5;
  border: 1px solid rgba(10,10,10,0.08);
  padding: 12px;
}

.metric-label {
  display: block;
  font-size: 10px;
  letter-spacing: 2px;
  text-transform: uppercase;
  color: rgba(10,10,10,0.5);
  margin-bottom: 6px;
}

.metric-value {
  font-size: 16px;
  font-weight: 700;
  color: #0A0A0A;
}

.timeline-item {
  padding: 14px;
  border: 1px solid rgba(10,10,10,0.08);
  background: #FAFAFA;
  margin-bottom: 10px;
}

.timeline-item-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}

.timeline-label,
.timeline-time {
  font-size: 11px;
  letter-spacing: 2px;
  text-transform: uppercase;
}

.timeline-label {
  color: #0A0A0A;
  font-weight: 700;
}

.timeline-time {
  color: rgba(10,10,10,0.45);
}

.timeline-item-body p,
.timeline-item-body pre {
  margin: 0;
  font-size: 12px;
  line-height: 1.55;
}

.timeline-item-body pre {
  margin-top: 8px;
  white-space: pre-wrap;
  background: #ffffff;
  border: 1px solid rgba(10,10,10,0.08);
  padding: 10px;
}

.completion-actions {
  margin-top: 18px;
}

.report-link-btn {
  border: 1px solid rgba(10,10,10,0.14);
  background: #ffffff;
  color: #0A0A0A;
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 2px;
  text-transform: uppercase;
  padding: 12px 16px;
  cursor: pointer;
}

.console-logs {
  border-top: 2px solid rgba(10,10,10,0.08);
  background: #0A0A0A;
  color: #FAFAFA;
}

.console-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  font-size: 11px;
  letter-spacing: 2px;
  text-transform: uppercase;
  cursor: pointer;
}

.console-body {
  max-height: 180px;
  overflow: auto;
  padding: 0 16px 16px;
}

.console-line {
  font-size: 12px;
  line-height: 1.5;
  padding-top: 8px;
  color: rgba(250,250,250,0.78);
}

.console-logs.collapsed .console-body {
  display: none;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

@media (max-width: 1100px) {
  .main-layout {
    grid-template-columns: 1fr;
  }

  .timeline-pane {
    border-left: none;
    border-top: 2px solid rgba(10,10,10,0.08);
  }
}
</style>