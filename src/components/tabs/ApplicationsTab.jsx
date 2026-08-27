import { useState, useEffect } from 'react'
import { api } from '../../api'
import { CheckCircle, AlertTriangle, XCircle, ChevronRight, RefreshCw } from 'lucide-react'

const STATUS_CONFIG = {
  healthy:  { icon: CheckCircle,   color: 'text-green-400',  bg: 'bg-green-400/10', label: 'Healthy'  },
  warning:  { icon: AlertTriangle, color: 'text-yellow-400', bg: 'bg-yellow-400/10',label: 'Warning'  },
  critical: { icon: XCircle,       color: 'text-red-400',    bg: 'bg-red-400/10',   label: 'Critical' },
}

function AppCard({ app, onClick, selected }) {
  const cfg = STATUS_CONFIG[app.status] || STATUS_CONFIG.healthy
  const Icon = cfg.icon
  return (
    <div
      onClick={() => onClick(app)}
      className={`p-4 rounded-xl border cursor-pointer transition-all
        ${selected
          ? 'border-blue-500 bg-blue-500/10'
          : 'border-[#30363d] bg-[#161b22] hover:border-[#58a6ff]'}`}
    >
      <div className="flex items-center justify-between mb-3">
        <span className="font-semibold text-white text-sm">{app.name}</span>
        <span className={`flex items-center gap-1 text-xs px-2 py-0.5 rounded-full ${cfg.bg} ${cfg.color}`}>
          <Icon size={11} /> {cfg.label}
        </span>
      </div>
      <div className="grid grid-cols-3 gap-2 text-center">
        <div>
          <div className="text-lg font-bold text-white">{app.total}</div>
          <div className="text-xs text-gray-400">Total</div>
        </div>
        <div>
          <div className={`text-lg font-bold ${app.errors > 0 ? 'text-red-400' : 'text-gray-400'}`}>
            {app.errors}
          </div>
          <div className="text-xs text-gray-400">Errors</div>
        </div>
        <div>
          <div className={`text-lg font-bold ${app.warnings > 0 ? 'text-yellow-400' : 'text-gray-400'}`}>
            {app.warnings}
          </div>
          <div className="text-xs text-gray-400">Warnings</div>
        </div>
      </div>
      {app.error_rate > 0 && (
        <div className="mt-3">
          <div className="flex justify-between text-xs text-gray-400 mb-1">
            <span>Error Rate</span>
            <span className="text-red-400">{app.error_rate}%</span>
          </div>
          <div className="h-1.5 bg-[#30363d] rounded-full">
            <div
              className="h-full bg-red-400 rounded-full transition-all"
              style={{ width: `${Math.min(app.error_rate, 100)}%` }}
            />
          </div>
        </div>
      )}
    </div>
  )
}

function SEV_BADGE({ sev }) {
  const colors = {
    CRITICAL: 'bg-red-500/20 text-red-400',
    ERROR:    'bg-red-400/20 text-red-300',
    WARNING:  'bg-yellow-400/20 text-yellow-300',
    INFO:     'bg-green-400/20 text-green-300',
    FATAL:    'bg-purple-400/20 text-purple-300',
  }
  return (
    <span className={`text-xs px-1.5 py-0.5 rounded font-mono ${colors[sev] || 'bg-gray-400/20 text-gray-300'}`}>
      {sev}
    </span>
  )
}

export default function ApplicationsTab({ liveData }) {
  const [apps, setApps]         = useState([])
  const [selected, setSelected] = useState(null)
  const [appLogs, setAppLogs]   = useState([])
  const [loading, setLoading]   = useState(false)

  const fetchApps = () => {
    api.apps().then(r => setApps(r.data.apps || []))
  }

  useEffect(() => {
    fetchApps()
    const t = setInterval(fetchApps, 5000)
    return () => clearInterval(t)
  }, [])

  useEffect(() => {
    if (liveData.latestLog) fetchApps()
  }, [liveData.latestLog])

  const selectApp = async (app) => {
    setSelected(app)
    setLoading(true)
    const r = await api.appLogs(app.name, 60)
    setAppLogs(r.data.logs || [])
    setLoading(false)
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-white">Applications</h1>
          <p className="text-sm text-gray-400 mt-0.5">EC2 server — {apps.length} services</p>
        </div>
        <button onClick={fetchApps}
          className="flex items-center gap-2 px-3 py-1.5 text-sm bg-[#21262d] hover:bg-[#30363d] border border-[#30363d] rounded-lg text-gray-300 transition">
          <RefreshCw size={14} /> Refresh
        </button>
      </div>

      {/* App cards */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        {apps.map(app => (
          <AppCard key={app.name} app={app}
            onClick={selectApp} selected={selected?.name === app.name} />
        ))}
      </div>

      {/* Selected app logs */}
      {selected && (
        <div className="bg-[#161b22] border border-[#30363d] rounded-xl p-4">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold text-white flex items-center gap-2">
              <ChevronRight size={16} className="text-blue-400" />
              {selected.name} — Live Logs
            </h2>
            <button onClick={() => selectApp(selected)}
              className="text-xs text-gray-400 hover:text-white transition">
              Refresh
            </button>
          </div>

          {loading ? (
            <div className="text-center text-gray-400 py-8">Loading...</div>
          ) : appLogs.length === 0 ? (
            <div className="text-center text-gray-500 py-8">No logs yet</div>
          ) : (
            <div className="space-y-1 max-h-96 overflow-y-auto font-mono text-xs">
              {appLogs.map((log, i) => (
                <div key={i}
                  className={`flex items-start gap-3 px-3 py-1.5 rounded hover:bg-[#21262d] transition
                    ${log.is_anomaly ? 'bg-red-500/5 border-l-2 border-red-500' : ''}`}>
                  <span className="text-gray-500 shrink-0 w-40">{log.timestamp?.slice(0,19)}</span>
                  <SEV_BADGE sev={log.severity} />
                  <span className={`flex-1 ${
                    log.severity === 'ERROR' || log.severity === 'CRITICAL' ? 'text-red-300' :
                    log.severity === 'WARNING' ? 'text-yellow-300' : 'text-gray-300'
                  }`}>{log.message?.slice(0, 120)}</span>
                  {log.is_anomaly && (
                    <span className="text-red-400 text-xs shrink-0">⚠ ANOMALY</span>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
