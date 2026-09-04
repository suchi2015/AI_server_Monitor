import { useState, useEffect, useRef } from 'react'
import { createWS } from './api'
import Sidebar from './components/Sidebar'
import ApplicationsTab from './components/tabs/ApplicationsTab'
import AIMonitorTab from './components/tabs/AIMonitorTab'
import HealthTab from './components/tabs/HealthTab'
import AlertsTab from './components/tabs/AlertsTab'
import LiveLogsTab from './components/tabs/LiveLogsTab'

export default function App() {
  const [activeTab, setActiveTab] = useState('applications')
  const [liveData, setLiveData]   = useState({
    latestLog: null, latestMetrics: null, latestAlert: null, latestIncident: null
  })
  const wsRef = useRef(null)

  useEffect(() => {
    const connect = () => {
      const ws = createWS(msg => {
        setLiveData(prev => ({
          ...prev,
          latestLog:      msg.type === 'log'      ? msg.data : prev.latestLog,
          latestMetrics:  msg.type === 'metrics'  ? msg.data : prev.latestMetrics,
          latestAlert:    msg.type === 'alert'    ? msg.data : prev.latestAlert,
          latestIncident: msg.type === 'incident' ? msg.data : prev.latestIncident,
        }))
      })
      ws.onclose = () => setTimeout(connect, 3000)
      wsRef.current = ws
    }
    connect()
    return () => wsRef.current?.close()
  }, [])

  const tabs = [
    { id: 'applications', label: 'Applications' },
    { id: 'ai-monitor',   label: 'AI Monitor'   },
    { id: 'live-logs',    label: 'Live Logs'     },
    { id: 'health',       label: 'CPU / RAM'     },
    { id: 'alerts',       label: 'Alerts'        },
  ]

  return (
    <div className="flex h-screen overflow-hidden bg-[#0d1117]">
      <Sidebar tabs={tabs} activeTab={activeTab} setActiveTab={setActiveTab}
               liveData={liveData} />
      <main className="flex-1 overflow-y-auto p-6">
        {activeTab === 'applications' && <ApplicationsTab liveData={liveData} />}
        {activeTab === 'ai-monitor'   && <AIMonitorTab   liveData={liveData} />}
        {activeTab === 'live-logs'    && <LiveLogsTab     liveData={liveData} />}
        {activeTab === 'health'       && <HealthTab       liveData={liveData} />}
        {activeTab === 'alerts'       && <AlertsTab       liveData={liveData} />}
      </main>
    </div>
  )
}
