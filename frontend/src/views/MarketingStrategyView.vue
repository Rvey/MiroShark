<template>
  <div class="main-view">
    <header class="app-header">
      <div class="header-left">
        <div class="brand" @click="router.push('/')">MIROSHARK</div>
      </div>

      <div class="header-center">
        <div class="view-switcher">
          <button
            v-for="mode in ['graph', 'network', 'workbench']"
            :key="mode"
            class="switch-btn"
            :class="{ active: viewMode === mode }"
            @click="viewMode = mode"
          >
            {{ { graph: 'Graph', network: 'Network', workbench: 'Workbench' }[mode] }}
          </button>
        </div>
      </div>

      <div class="header-right">
        <div class="workflow-step">
          <span class="step-num">Step 4/5</span>
          <span class="step-name">Marketing Strategy</span>
        </div>
        <div class="step-divider"></div>
        <span class="status-indicator" :class="statusClass">
          <span class="dot"></span>
          {{ statusText }}
        </span>
      </div>
    </header>

    <main class="content-area">
      <div class="panel-wrapper left" :style="leftPanelStyle">
        <GraphPanel
          v-if="viewMode !== 'network'"
          :graphData="graphData"
          :loading="graphLoading"
          :currentPhase="4"
          :isSimulating="false"
          :simulationId="simulationId"
          @refresh="refreshGraph"
          @toggle-maximize="toggleMaximize('graph')"
        />
        <NetworkPanel
          v-else
          :simulationId="simulationId"
          :isSimulating="false"
        />
      </div>

      <div class="panel-wrapper right" :style="rightPanelStyle">
        <Step4MarketingStrategy
          :strategyId="currentStrategyId"
          :simulationId="simulationId"
          :systemLogs="systemLogs"
          @add-log="addLog"
          @update-status="updateStatus"
        />
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import GraphPanel from '../components/GraphPanel.vue'
import NetworkPanel from '../components/NetworkPanel.vue'
import Step4MarketingStrategy from '../components/Step4MarketingStrategy.vue'
import { getProject, getGraphData } from '../api/graph'
import { getSimulation } from '../api/simulation'
import { getMarketingStrategy } from '../api/marketingStrategy'

const route = useRoute()
const router = useRouter()

defineProps({
  strategyId: String
})

const viewMode = ref('workbench')
const currentStrategyId = ref(route.params.strategyId)
const simulationId = ref(null)
const projectData = ref(null)
const graphData = ref(null)
const graphLoading = ref(false)
const systemLogs = ref([])
const currentStatus = ref('processing')

const leftPanelStyle = computed(() => {
  if (viewMode.value === 'graph' || viewMode.value === 'network') return { width: '100%', opacity: 1, transform: 'translateX(0)' }
  if (viewMode.value === 'workbench') return { width: '0%', opacity: 0, transform: 'translateX(-20px)' }
  return { width: '50%', opacity: 1, transform: 'translateX(0)' }
})

const rightPanelStyle = computed(() => {
  if (viewMode.value === 'workbench') return { width: '100%', opacity: 1, transform: 'translateX(0)' }
  if (viewMode.value === 'graph' || viewMode.value === 'network') return { width: '0%', opacity: 0, transform: 'translateX(20px)' }
  return { width: '50%', opacity: 1, transform: 'translateX(0)' }
})

const statusClass = computed(() => currentStatus.value)

const statusText = computed(() => {
  if (currentStatus.value === 'error') return 'Error'
  if (currentStatus.value === 'completed') return 'Completed'
  return 'Generating'
})

const addLog = (msg) => {
  const now = new Date()
  const time = now.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })
  systemLogs.value.push({ time: `${time}.${String(now.getMilliseconds()).padStart(3, '0')}`, msg })
  if (systemLogs.value.length > 200) {
    systemLogs.value.shift()
  }
}

const updateStatus = (status) => {
  currentStatus.value = status
}

const toggleMaximize = (target) => {
  if (viewMode.value === target) {
    viewMode.value = 'workbench'
    return
  }
  viewMode.value = target
}

const loadGraph = async (graphId) => {
  graphLoading.value = true
  try {
    const res = await getGraphData(graphId)
    if (res.success) {
      graphData.value = res.data
      addLog('Graph data loaded successfully')
    }
  } catch (error) {
    addLog(`Failed to load graph: ${error.message}`)
  } finally {
    graphLoading.value = false
  }
}

const refreshGraph = () => {
  if (projectData.value?.graph_id) {
    loadGraph(projectData.value.graph_id)
  }
}

const loadStrategyData = async () => {
  try {
    addLog(`Loading marketing strategy: ${currentStrategyId.value}`)
    const strategyRes = await getMarketingStrategy(currentStrategyId.value)
    if (!strategyRes.success || !strategyRes.data) {
      addLog(`Failed to load marketing strategy: ${strategyRes.error || 'Unknown error'}`)
      return
    }

    simulationId.value = strategyRes.data.simulation_id
    if (!simulationId.value) return

    const simRes = await getSimulation(simulationId.value)
    if (!simRes.success || !simRes.data || !simRes.data.project_id) return

    const projectRes = await getProject(simRes.data.project_id)
    if (projectRes.success && projectRes.data) {
      projectData.value = projectRes.data
      addLog(`Project loaded successfully: ${projectRes.data.project_id}`)
      if (projectRes.data.graph_id) {
        await loadGraph(projectRes.data.graph_id)
      }
    }
  } catch (error) {
    addLog(`Loading error: ${error.message}`)
  }
}

watch(() => route.params.strategyId, (newId) => {
  if (newId && newId !== currentStrategyId.value) {
    currentStrategyId.value = newId
    loadStrategyData()
  }
}, { immediate: true })

onMounted(() => {
  addLog('MarketingStrategyView initialized')
  loadStrategyData()
})
</script>

<style scoped>
.main-view {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: #FAFAFA;
  overflow: hidden;
  font-family: var(--font-display);
}

.app-header {
  height: 60px;
  border-bottom: 2px solid rgba(10,10,10,0.08);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 22px;
  background: #0A0A0A;
  z-index: 100;
  position: relative;
}

.header-center {
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
}

.brand {
  font-family: var(--font-mono);
  font-weight: 800;
  font-size: 18px;
  letter-spacing: 3px;
  text-transform: uppercase;
  cursor: pointer;
  color: #FAFAFA;
}

.view-switcher {
  display: flex;
  background: rgba(250,250,250,0.08);
  padding: 4px;
  gap: 4px;
}

.switch-btn {
  border: 2px solid transparent;
  background: transparent;
  padding: 6px 16px;
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 3px;
  color: rgba(250,250,250,0.5);
  cursor: pointer;
  transition: all 0.2s;
}

.switch-btn.active {
  background: #0A0A0A;
  color: #FAFAFA;
  border: 2px solid #FF6B1A;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.workflow-step {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
}

.step-num {
  font-family: var(--font-mono);
  font-weight: 700;
  color: rgba(250,250,250,0.4);
}

.step-name {
  font-weight: 700;
  color: #FAFAFA;
}

.step-divider {
  width: 1px;
  height: 14px;
  background-color: rgba(250,250,250,0.12);
}

.status-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  font-family: var(--font-mono);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 3px;
  color: rgba(250,250,250,0.5);
  font-weight: 500;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: rgba(250,250,250,0.2);
}

.status-indicator.processing .dot { background: #FF6B1A; animation: pulse 1s infinite; }
.status-indicator.completed .dot { background: #43C165; }
.status-indicator.error .dot { background: #FF4444; }

@keyframes pulse { 50% { opacity: 0.5; } }

.content-area {
  flex: 1;
  display: flex;
  position: relative;
  overflow: hidden;
}

.panel-wrapper {
  height: 100%;
  overflow: hidden;
  transition: width 0.4s cubic-bezier(0.25, 0.8, 0.25, 1), opacity 0.3s ease, transform 0.3s ease;
  will-change: width, opacity, transform;
}

.panel-wrapper.left {
  border-right: 2px solid rgba(10,10,10,0.08);
}
</style>