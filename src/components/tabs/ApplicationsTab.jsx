import { useState, useEffect, useRef } from 'react'
import { api } from '../../api'
import { CheckCircle, AlertTriangle, XCircle, ChevronRight, RefreshCw, Activity } from 'lucide-react'

const STATUS_CONFIG = {
  healthy:  { icon: CheckCircle,   color: 'text-green-400',  bg: 'bg-green-400/10', label: 'Healthy'  },
  warning:  { icon: AlertTriangle, color: 'text-yellow-400', bg: 'bg-yellow-400/10',label: 'Warning'  },
  critical: { icon: XCircle,       color: 'text-red-400',    bg: 'bg-red-400/10',   label: 'Critical' },
}

// Color for each severity level
const SEV_COLOR = {
  CRITICAL: 'text-red-400',
  FATAL:    'text-red-400',
  ERROR:    'text-red-300',
  WARNING:  'text-yellow-300',
  WARN:     'text-yellow-300',
  INFO:     'text-gray-300',
  DEBUG:    'text-gray-500',
}

const SEV_BG = {
  CRITICAL: 'bg-red-500/10 border-l-2 border-red-500',
  FATAL:    'bg-red-500/10 border-l-2 border-red-500',
  ERROR:    'bg-red-400/5  border-l-2 border-red-400',
  WARNING:  'bg-yellow-400/5 border-l-2 border-yellow-400',
  WARN:     'bg-yellow-400/5 border-l-2 border-yellow-400',
  INFO:     '',
  DEBUG:    '',
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

function SevBadge({ sev }) {
  const colors = {
    CRITICAL: 'bg-red-500/20 text-red-400',
    FATAL:    'bg-purple-500/20 text-purple-400',
    ERROR:    'bg-red-400/20 text-red-300',
    WARNING:  'bg-yellow-400/20 text-yellow-300',
    WARN:     'bg-yellow-400/20 text-yellow-300',
    INFO:     'bg-green-400/10 text-green-400',
    DEBUG:    'bg-gray-400/10 text-gray-400',
  }
  return (
    <span className={`text-xs px-1.5 py-0.5 rounded font-mono shrink-0 ${colors[sev] || 'bg-gray-400/20 text-gray-300'}`}>
      {sev}
    </span>
  )
}

function LogRow({ log }) {
  const sev = log.severity || 'INFO'
  const rowBg = SEV_BG[sev] || ''
  const textColor = SEV_COLOR[sev] || 'text-gray-300'
  return (
    <div className={`flex items-start gap-2 px-3 py-1.5 rounded hover:bg-[#21262d] transition font-mono text-xs ${rowBg}`}>
      <span className="text-gray-600 shrink-0 w-20">{log.timestamp?.slice(11, 19)}</span>
      <SevBadge sev={sev} />
      <span className={`flex-1 break-all ${textColor}`}>{log.raw || log.message}</span>
      {log.is_anomaly && (
        <span className="text-red-400 text-xs shrink-0 ml-1">⚠</span>
      )}
    </div>
  )
}

export default function ApplicationsTab({ liveData }) {
  const [apps, setApps]           = useState([])
  const [selected, setSelected]   = useState(null)
  const [appLogs, setAppLogs]     = useState([])
  const [loading, setLoading]     = useState(false)
  const [autoScroll, setAutoScroll] = useState(true)
  const [sevFilter, setSevFilter] = useState('all')
  const logsEndRef = useRef(null)
  const pollingRef = useRef(null)

  const fetchApps = () => {
    api.apps().then(r => setApps(r.data.apps || []))
  }

  useEffect(() => {
    fetchApps()
    const t = setInterval(fetchApps, 5000)
    return () => clearInterval(t)
  }, [])

  // Auto-refresh logs when new live log comes in for selected app
  useEffect(() => {
    if (liveData.latestLog) {
      fetchApps()
      if (selected && liveData.latestLog.app === selected.name) {
        setAppLogs(prev => {
          const next = [liveData.latestLog, ...prev].slice(0, 200)
          return next
        })
      }
    }
  }, [liveData.latestLog])

  // Auto-scroll to top (newest logs at top)
  useEffect(() => {
    if (autoScroll && logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [appLogs, autoScroll])

  const selectApp = async (app) => {
    setSelected(app)
    setLoading(true)
    setSevFilter('all')
    // fetch last 200 logs (all severities)
    const r = await api.appLogs(app.name, 200)
    setAppLogs(r.data.logs || [])
    setLoading(false)

    // Poll every 3s for new logs
    if (pollingRef.current) clearInterval(pollingRef.current)
    pollingRef.current = setInterval(async () => {
      const r2 = await api.appLogs(app.name, 200)
      setAppLogs(r2.data.logs || [])
    }, 3000)
  }

  useEffect(() => {
    return () => { if (pollingRef.current) clearInterval(pollingRef.current) }
  }, [])

  const filtered = sevFilter === 'all'
    ? appLogs
    : appLogs.filter(l => (l.severity || 'INFO') === sevFilter)

  const errorCount   = appLogs.filter(l => ['ERROR','CRITICAL','FATAL'].includes(l.severity)).length
  const warningCount = appLogs.filter(l => ['WARNING','WARN'].includes(l.severity)).length
  const infoCount    = appLogs.filter(l => ['INFO','DEBUG'].includes(l.severity) || !l.severity).length

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-white">Applications</h1>
          <p className="text-sm text-gray-400 mt-0.5">EC2 server — {apps.length} services monitored</p>
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

      {/* Selected app log viewer */}
      {selected && (
        <div className="bg-[#161b22] border border-[#30363d] rounded-xl overflow-hidden">
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-[#30363d]">
            <div className="flex items-center gap-3">
              <Activity size={14} className="text-green-400 animate-pulse" />
              <span className="font-semibold text-white text-sm">{selected.name} — Live Logs</span>
              <span className="text-xs text-gray-500">{appLogs.length} entries</span>
            </div>
            <div className="flex items-center gap-2">
              {/* Severity filter buttons */}
              {[
                { key: 'all',     label: `All (${appLogs.length})`,      color: 'text-gray-300' },
                { key: 'ERROR',   label: `Errors (${errorCount})`,       color: 'text-red-400'  },
                { key: 'WARNING', label: `Warnings (${warningCount})`,   color: 'text-yellow-400' },
                { key: 'INFO',    label: `Info (${infoCount})`,          color: 'text-green-400' },
              ].map(f => (
                <button key={f.key} onClick={() => setSevFilter(f.key)}
                  className={`text-xs px-2.5 py-1 rounded-full transition
                    ${sevFilter === f.key
                      ? 'bg-blue-600 text-white'
                      : `bg-[#21262d] hover:bg-[#30363d] ${f.color}`}`}>
                  {f.label}
                </button>
              ))}
              <button
                onClick={() => setAutoScroll(v => !v)}
                className={`text-xs px-2.5 py-1 rounded-full transition border
                  ${autoScroll
                    ? 'border-green-500/50 text-green-400 bg-green-500/10'
                    : 'border-[#30363d] text-gray-500 bg-[#21262d]'}`}>
                {autoScroll ? '⬇ Auto-scroll ON' : '⬇ Auto-scroll OFF'}
              </button>
            </div>
          </div>

          {/* Log output — terminal style */}
          <div className="bg-[#0d1117] max-h-[500px] overflow-y-auto p-2 space-y-0.5">
            {loading ? (
              <div className="text-center text-gray-500 py-12">Loading logs...</div>
            ) : filtered.length === 0 ? (
              <div className="text-center text-gray-600 py-12 font-mono text-sm">
                No logs yet — waiting for {selected.name} to write logs...
              </div>
            ) : (
              <>
                {filtered.map((log, i) => <LogRow key={i} log={log} />)}
                <div ref={logsEndRef} />
              </>
            )}
          </div>

          {/* Footer stats bar */}
          <div className="flex items-center gap-4 px-4 py-2 border-t border-[#30363d] bg-[#161b22]">
            <span className="text-xs text-gray-500">Showing: <span className="text-white">{filtered.length}</span></span>
            <span className="text-xs text-red-400">Errors: <span className="font-bold">{errorCount}</span></span>
            <span className="text-xs text-yellow-400">Warnings: <span className="font-bold">{warningCount}</span></span>
            <span className="text-xs text-green-400">Info/200s: <span className="font-bold">{infoCount}</span></span>
            <span className="ml-auto text-xs text-gray-600">Updates every 3s</span>
          </div>
        </div>
      )}

      {!selected && apps.length > 0 && (
        <div className="text-center py-12 text-gray-600 text-sm">
          ↑ Click an application card to view its logs
        </div>
      )}
    </div>
  )
}
