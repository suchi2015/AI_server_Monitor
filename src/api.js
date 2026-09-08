import axios from 'axios'

const BASE = import.meta.env.VITE_API_URL || 'http://15.206.180.134/AIMonitor-api'

export const api = {
  status:          () => axios.get(`${BASE}/status`),
  apps:            () => axios.get(`${BASE}/apps`),
  appLogs:         (app, limit=200) => axios.get(`${BASE}/apps/${app}/logs?limit=${limit}`),
  appAnomalies:    (app, limit=20)  => axios.get(`${BASE}/apps/${app}/anomalies?limit=${limit}`),
  logs:            (limit=200)      => axios.get(`${BASE}/logs?limit=${limit}`),
  anomalies:       (limit=50)       => axios.get(`${BASE}/anomalies?limit=${limit}`),
  metrics:         (limit=60)       => axios.get(`${BASE}/metrics?limit=${limit}`),
  alerts:          (limit=100)      => axios.get(`${BASE}/alerts?limit=${limit}`),
  incidents:       (limit=50)       => axios.get(`${BASE}/incidents?limit=${limit}`),
  openIncidents:   ()               => axios.get(`${BASE}/incidents/open`),
  resolveIncident: (id)             => axios.post(`${BASE}/incidents/${id}/resolve`),
  clearIncidents:  ()               => axios.delete(`${BASE}/incidents`),
  train:           (epochs=30)      => axios.post(`${BASE}/train`, { epochs }),

  // Thresholds
  getThresholds:   ()               => axios.get(`${BASE}/thresholds`),
  setThresholds:   (data)           => axios.post(`${BASE}/thresholds`, data),

  // Escalations
  escalations:     ()               => axios.get(`${BASE}/escalations`),
}

export function createWS(onMessage) {
  const wsUrl = import.meta.env.VITE_WS_URL || 'ws://15.206.180.134/AIMonitor-ws/live'
  const ws = new WebSocket(wsUrl)
  ws.onmessage = e => { try { onMessage(JSON.parse(e.data)) } catch {} }
  ws.onerror   = () => console.warn('WS error')
  return ws
}
