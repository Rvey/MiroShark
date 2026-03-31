import service, { requestWithRetry } from './index'

export const generateMarketingStrategy = (data) => {
  return requestWithRetry(() => service.post('/api/marketing-strategy/generate', data), 3, 1000)
}

export const getMarketingStrategyStatus = (data) => {
  return requestWithRetry(() => service.post('/api/marketing-strategy/generate/status', data), 3, 1000)
}

export const getMarketingStrategy = (strategyId) => {
  return service.get(`/api/marketing-strategy/${strategyId}`)
}

export const getMarketingStrategyByReport = (reportId) => {
  return service.get(`/api/marketing-strategy/by-report/${reportId}`)
}

export const getMarketingStrategyAgentLog = (strategyId, fromLine = 0) => {
  return service.get(`/api/marketing-strategy/${strategyId}/agent-log`, { params: { from_line: fromLine } })
}

export const getMarketingStrategyConsoleLog = (strategyId, fromLine = 0) => {
  return service.get(`/api/marketing-strategy/${strategyId}/console-log`, { params: { from_line: fromLine } })
}