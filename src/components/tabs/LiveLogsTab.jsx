import { useState, useEffect, useRef } from 'react'
import { api } from '../../api'
import { Terminal, Pause, Play, Trash2, Download } from 'lucide-react'

const SEV_COLOR = {
  CRITICAL: 'text-red-400',
  FATAL:    'text-red-400',
  ERROR:    'text-red-300',
  WARNING:  'text-yellow-300',
  WARN:     'text-yellow-300',
  INFO:     'text-gray-300',
  DEBUG:    'text-gray-500',
}

const SEV_ROW_BG = {
  CRITICAL: 'bg-red-500/10 border-l-2 border-red-500',
  FATAL:    'bg-red-500/10 border-l-2 border-red-500',
  ERROR:    'bg-red-400/5  border-l-2 border-red-400',
  WARNING:  'bg-yellow-400/5 border-l-2 border-yellow-500',
  WARN:     'bg-yellow-400/5 border-l-2 border-yellow-500',
  INFO:     '',
  DEBUG:    '',
}

const APP_COLORS = [
  'text-blue-400', 'text-purple-400', 'text-cyan-400',
  'text-pink-400', 'text-orange-400', 'text-teal-400',
]

const SEV_BADGE_COLORS = {
  CRITICAL: 'bg-red-500/20 text-red-400',
  FATAL:    'bg-purple-500/20 text-purple-400',
  ERROR:    'bg-red-400/20 text-red-300',
  WARNING:  'bg-yellow-400/20 text-yellow-300',
  WARN:     'bg-yellow-400/20 text-yellow-300',
  INFO:     'bg-gray-400/10 text-gray-400',
  DEBUG:    'bg-gray-600/20 text-gray-600',
}

function SevBadge({ sev }) {
  return (
    <span className={`text-xs px-1.5 py-0.5 rounded font-mono w-16 text-center inline-block shrink-0
      ${SEV_BADGE_COLORS[sev] || 'bg-gray-400/20 text-gray-300'}`}>
      {sev?.slice(0, 4)}
    </span>
  )
}

export default function LiveLogsTab({ liveData }) {
  const [logs, setLogs]           = useState([])
  const [paused, setPaused]       = useState(false)
  const [sevFilter, setSevFilter] = useState('all')
  const [appFilter, setAppFilter] = useState('all')
  const [apps, setApps]           = useState([])
  const [autoScroll, setAutoScroll] = useState(true)
  const bottomRef = useRef(null)
  const pausedRef = useRef(false)
  const appColorMap = useRef({})

  // Assign stable color to each app name
  const getAppColor = (name) => {
    if (!appColorMap.current[name]) {
      const idx = Object.keys(appColorMap.current).length % APP_COLORS.length
      appColorMap.current[name] = APP_COLORS[idx]
    }
    return appColorMap.current[name]
  }

  // Initial load — fetch last 200 logs from all apps
  useEffect(() => {
    api.apps().then(r => {
      const appList = (r.data.apps || []).map(a => a.name)
      setApps(appList)
      // fetch logs for all apps
      Promise.all(appList.map(name => api.appLogs(name, 100))).then(results => {
        const allLogs = results.flatMap((r, i) =>
          (r.data.logs || []).map(l => ({ ...l, app: l.app || appList[i] }))
        )
        // Sort by timestamp ascending (oldest first, newest at bottom)
        allLogs.sort((a, b) =>
          (a.timestamp || '').localeCompare(b.timestamp || '')
        )
        setLogs(allLogs.slice(-300))
      })
    })
  }, [])

  // Live feed — append new logs via WebSocket
  useEffect(() => {
    if (liveData.latestLog && !pausedRef.current) {
      const entry = liveData.latestLog
      setLogs(prev => {
        const next = [...prev, entry]
        return next.slice(-500) // keep last 500
      })
    }
  }, [liveData.latestLog])

  useEffect(() => {
    pausedRef.current = paused
  }, [paused])

  // Auto-scroll to bottom
  useEffect(() => {
    if (autoScroll && bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [logs, autoScroll])

  const clearLogs = () => setLogs([])

  const downloadLogs = () => {
    const text = logs.map(l =>
      `${l.timestamp} [${l.app}] ${l.severity} ${l.raw || l.message}`
    ).join('\n')
    const blob = new Blob([text], { type: 'text/plain' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = `logs-${new Date().toISOString().slice(0,19)}.txt`
    a.click()
  }

  // Filter
  const filtered = logs.filter(l => {
    const sevMatch = sevFilter === 'all' || (l.severity || 'INFO') === sevFilter
    const appMatch = appFilter === 'all' || l.app === appFilter
    return sevMatch && appMatch
  })

  const counts = {
    all:      logs.length,
    ERROR:    logs.filter(l => ['ERROR','CRITICAL','FATAL'].includes(l.severity)).length,
    WARNING:  logs.filter(l => ['WARNING','WARN'].includes(l.severity)).length,
    INFO:     logs.filter(l => ['INFO','DEBUG'].includes(l.severity) || !l.severity).length,
  }

  return (
    <div className="flex flex-col h-full gap-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Terminal size={20} className="text-green-400" />
          <h1 className="text-xl font-bold text-white">Live Logs</h1>
          <span className="text-xs px-2 py-0.5 bg-green-500/20 text-green-400 rounded-full">
            {filtered.length} lines
          </span>
          {paused && (
            <span className="text-xs px-2 py-0.5 bg-yellow-500/20 text-yellow-400 rounded-full">
              ⏸ Paused
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => setPaused(v => !v)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs transition border
              ${paused
                ? 'bg-green-600 border-green-500 text-white hover:bg-green-700'
                : 'bg-[#21262d] border-[#30363d] text-gray-300 hover:bg-[#30363d]'}`}>
            {paused ? <><Play size={12}/> Resume</> : <><Pause size={12}/> Pause</>}
          </button>
          <button onClick={downloadLogs}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs bg-[#21262d] border border-[#30363d] text-gray-300 hover:bg-[#30363d] transition">
            <Download size={12}/> Export
          </button>
          <button onClick={clearLogs}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs bg-[#21262d] border border-[#30363d] text-gray-400 hover:text-red-400 hover:bg-red-500/10 transition">
            <Trash2 size={12}/> Clear
          </button>
        </div>
      </div>

      {/* Filter bar */}
      <div className="flex items-center gap-3 flex-wrap">
        {/* Severity filters */}
        <div className="flex items-center gap-1.5">
          {[
            { key: 'all',     label: `All (${counts.all})` },
            { key: 'ERROR',   label: `Error (${counts.ERROR})`,   cls: 'data-active:bg-red-600' },
            { key: 'WARNING', label: `Warn (${counts.WARNING})`,  cls: 'data-active:bg-yellow-600' },
            { key: 'INFO',    label: `Info (${counts.INFO})`,     cls: 'data-active:bg-green-700' },
          ].map(f => (
            <button key={f.key} onClick={() => setSevFilter(f.key)}
              className={`text-xs px-3 py-1 rounded-full transition
                ${sevFilter === f.key
                  ? f.key === 'ERROR'   ? 'bg-red-600 text-white'
                  : f.key === 'WARNING' ? 'bg-yellow-600 text-white'
                  : f.key === 'INFO'    ? 'bg-green-700 text-white'
                  : 'bg-blue-600 text-white'
                  : 'bg-[#21262d] text-gray-400 hover:text-white'}`}>
              {f.label}
            </button>
          ))}
        </div>

        <div className="w-px h-4 bg-[#30363d]" />

        {/* App filters */}
        <div className="flex items-center gap-1.5">
          <button onClick={() => setAppFilter('all')}
            className={`text-xs px-3 py-1 rounded-full transition
              ${appFilter === 'all' ? 'bg-gray-600 text-white' : 'bg-[#21262d] text-gray-400 hover:text-white'}`}>
            All Apps
          </button>
          {apps.map(name => (
            <button key={name} onClick={() => setAppFilter(name)}
              className={`text-xs px-3 py-1 rounded-full transition
                ${appFilter === name
                  ? 'bg-blue-600 text-white'
                  : `bg-[#21262d] ${getAppColor(name)} hover:bg-[#30363d]`}`}>
              {name}
            </button>
          ))}
        </div>

        <div className="ml-auto">
          <button onClick={() => setAutoScroll(v => !v)}
            className={`text-xs px-2.5 py-1 rounded-full transition border
              ${autoScroll
                ? 'border-green-500/50 text-green-400 bg-green-500/10'
                : 'border-[#30363d] text-gray-500 bg-[#21262d]'}`}>
            ⬇ {autoScroll ? 'Auto-scroll ON' : 'Auto-scroll OFF'}
          </button>
        </div>
      </div>

      {/* Terminal output */}
      <div className="flex-1 bg-[#0d1117] border border-[#30363d] rounded-xl overflow-y-auto font-mono text-xs p-2 space-y-0.5 min-h-0"
        style={{ maxHeight: 'calc(100vh - 260px)' }}>
        {filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-48 text-gray-600">
            <Terminal size={28} className="mb-3 opacity-40" />
            <p>Waiting for logs from your applications...</p>
            <p className="text-xs mt-1 opacity-60">Make sure your apps are writing to log files and backend is running</p>
          </div>
        ) : (
          <>
            {filtered.map((log, i) => {
              const sev = log.severity || 'INFO'
              const rowBg = SEV_ROW_BG[sev] || ''
              const textColor = SEV_COLOR[sev] || 'text-gray-300'
              const appColor = getAppColor(log.app || 'unknown')
              return (
                <div key={i}
                  className={`flex items-start gap-2 px-2 py-1 rounded hover:bg-white/5 transition group ${rowBg}`}>
                  {/* Timestamp */}
                  <span className="text-gray-600 shrink-0 w-20">
                    {log.timestamp?.slice(11, 19) || '??:??:??'}
                  </span>
                  {/* App name */}
                  <span className={`shrink-0 w-28 truncate font-semibold ${appColor}`}>
                    {log.app || 'unknown'}
                  </span>
                  {/* Severity badge */}
                  <SevBadge sev={sev} />
                  {/* Log message — full raw line */}
                  <span className={`flex-1 break-all leading-relaxed ${textColor}`}>
                    {log.raw || log.message || ''}
                  </span>
                  {/* Anomaly marker */}
                  {log.is_anomaly && (
                    <span className="text-red-400 shrink-0 opacity-0 group-hover:opacity-100 transition">⚠</span>
                  )}
                </div>
              )
            })}
            <div ref={bottomRef} />
          </>
        )}
      </div>

      {/* Status bar */}
      <div className="flex items-center gap-4 text-xs text-gray-600 px-1">
        <span className="text-red-400/70">● Errors: {counts.ERROR}</span>
        <span className="text-yellow-400/70">● Warnings: {counts.WARNING}</span>
        <span className="text-green-400/70">● Info/200s: {counts.INFO}</span>
        <span className="ml-auto">Buffer: {logs.length}/500 lines</span>
      </div>
    </div>
  )
}
