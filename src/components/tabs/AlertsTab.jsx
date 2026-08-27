import { useState, useEffect } from 'react'
import { api } from '../../api'
import { Bell, CheckCircle, AlertTriangle, XCircle, Activity } from 'lucide-react'

const SEV_CONFIG = {
  CRITICAL: { icon: XCircle,       color: 'text-red-400',    bg: 'bg-red-400/10',    border: 'border-red-500/30'    },
  HIGH:     { icon: XCircle,       color: 'text-red-300',    bg: 'bg-red-300/10',    border: 'border-red-400/30'    },
  ERROR:    { icon: AlertTriangle, color: 'text-red-300',    bg: 'bg-red-300/10',    border: 'border-red-400/30'    },
  WARNING:  { icon: AlertTriangle, color: 'text-yellow-400', bg: 'bg-yellow-400/10', border: 'border-yellow-500/30' },
  INFO:     { icon: CheckCircle,   color: 'text-green-400',  bg: 'bg-green-400/10',  border: 'border-green-500/30'  },
}

function AlertRow({ alert }) {
  const sev = alert.severity || 'INFO'
  const cfg = SEV_CONFIG[sev] || SEV_CONFIG.INFO
  const Icon = cfg.icon
  return (
    <div className={`flex items-start gap-3 p-3 rounded-lg border ${cfg.bg} ${cfg.border}`}>
      <Icon size={16} className={`${cfg.color} mt-0.5 shrink-0`} />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className={`text-xs font-semibold px-1.5 py-0.5 rounded ${cfg.bg} ${cfg.color}`}>
            {sev}
          </span>
          <span className="text-xs text-gray-400">[{alert.type?.toUpperCase()}]</span>
          {alert.app && <span className="text-xs text-blue-400">{alert.app}</span>}
          {alert.metric && <span className="text-xs text-gray-400">{alert.metric}</span>}
        </div>
        <p className="text-sm text-gray-200 mt-1">{alert.message}</p>
        {alert.value !== undefined && (
          <p className="text-xs text-gray-400 mt-0.5">
            Value: <span className={cfg.color}>{alert.value?.toFixed?.(1) ?? alert.value}</span>
            {alert.threshold && <> / Threshold: {alert.threshold}</>}
          </p>
        )}
      </div>
      <span className="text-xs text-gray-500 shrink-0 ml-2">
        {alert.timestamp?.slice(11,19)}
      </span>
    </div>
  )
}

export default function AlertsTab({ liveData }) {
  const [alerts, setAlerts]     = useState([])
  const [filter, setFilter]     = useState('all')
  const [status, setStatus]     = useState({})

  const fetchAlerts = () => {
    api.alerts(100).then(r => setAlerts(r.data.alerts || []))
    api.status().then(r => setStatus(r.data))
  }

  useEffect(() => {
    fetchAlerts()
    const t = setInterval(fetchAlerts, 5000)
    return () => clearInterval(t)
  }, [])

  useEffect(() => {
    if (liveData.latestAlert)
      setAlerts(prev => [liveData.latestAlert, ...prev].slice(0, 100))
  }, [liveData.latestAlert])

  const filtered = filter === 'all' ? alerts
    : alerts.filter(a => a.severity === filter || a.type === filter)

  const critCount = alerts.filter(a => a.severity === 'CRITICAL').length
  const warnCount = alerts.filter(a => a.severity === 'WARNING').length

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <div className="flex items-center gap-2">
            <Bell className="text-yellow-400" size={20} />
            <h1 className="text-xl font-bold text-white">Alerts</h1>
          </div>
          <p className="text-sm text-gray-400 mt-0.5">
            {alerts.length} total — {critCount} critical — {warnCount} warnings
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Activity size={14} className="text-green-400 animate-pulse" />
          <span className="text-xs text-gray-400">Live</span>
        </div>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-4 gap-3 mb-6">
        {[
          { label: 'Total Logs',   val: status.total_logs      || 0, color: 'text-white'       },
          { label: 'Anomalies',    val: status.total_anomalies || 0, color: 'text-orange-400'  },
          { label: 'Alerts',       val: status.total_alerts    || 0, color: 'text-yellow-400'  },
          { label: 'Incidents',    val: status.open_incidents  || 0, color: 'text-red-400'     },
        ].map(({ label, val, color }) => (
          <div key={label} className="bg-[#161b22] border border-[#30363d] rounded-xl p-4 text-center">
            <div className={`text-2xl font-bold ${color}`}>{val}</div>
            <div className="text-xs text-gray-400 mt-1">{label}</div>
          </div>
        ))}
      </div>

      {/* Filter */}
      <div className="flex gap-2 mb-4">
        {['all','CRITICAL','WARNING','threshold','anomaly'].map(f => (
          <button key={f} onClick={() => setFilter(f)}
            className={`px-3 py-1 rounded-full text-xs transition
              ${filter === f
                ? 'bg-blue-600 text-white'
                : 'bg-[#21262d] text-gray-400 hover:text-white'}`}>
            {f.charAt(0).toUpperCase() + f.slice(1)}
          </button>
        ))}
      </div>

      {/* Alerts list */}
      <div className="space-y-2">
        {filtered.length === 0 ? (
          <div className="text-center py-16 text-gray-500">
            <CheckCircle size={32} className="text-green-400 mx-auto mb-2" />
            <p>No alerts. All systems healthy.</p>
          </div>
        ) : (
          filtered.map((a, i) => <AlertRow key={i} alert={a} />)
        )}
      </div>
    </div>
  )
}
