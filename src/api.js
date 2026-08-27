import axios from 'axios'

const BASE = '/api'

export const api = {
  status:         () => axios.get(`${BASE}/status`),
  apps:           () => axios.get(`${BASE}/apps`),
  appLogs:        (app, limit=50) => axios.get(`${BASE}/apps/${app}/logs?limit=${limit}`),
  appAnomalies:   (app, limit=20) => axios.get(`${BASE}/apps/${app}/anomalies?limit=${limit}`),
  logs:           (limit=100)     => axios.get(`${BASE}/logs?limit=${limit}`),
  anomalies:      (limit=50)      => axios.get(`${BASE}/anomalies?limit=${limit}`),
  metrics:        (limit=60)      => axios.get(`${BASE}/metrics?limit=${limit}`),
  alerts:         (limit=50)      => axios.get(`${BASE}/alerts?limit=${limit}`),
  incidents:      (limit=50)      => axios.get(`${BASE}/incidents?limit=${limit}`),
  openIncidents:  ()              => axios.get(`${BASE}/incidents/open`),
  resolveIncident:(id)            => axios.post(`${BASE}/incidents/${id}/resolve`),
  train:          (epochs=30)     => axios.post(`${BASE}/train`, { epochs }),
}

export function createWS(onMessage) {
  const ws = new WebSocket(`ws://${window.location.hostname}:8000/ws/live`)
  ws.onmessage = e => { try { onMessage(JSON.parse(e.data)) } catch {} }
  ws.onerror   = () => console.warn('WS error')
  return ws
}
