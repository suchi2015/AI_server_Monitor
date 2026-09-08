import { useState, useEffect } from 'react'
import { api } from '../../api'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine, AreaChart, Area
} from 'recharts'
import { Cpu, MemoryStick, HardDrive, Wifi, Pencil, Check, X } from 'lucide-react'

// ── Save confirmation popup ───────────────────────────────────────────────────
function SavePopup({ metric, oldVal, newVal, onConfirm, onCancel }) {
  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
      <div className="bg-[#161b22] border border-[#30363d] rounded-xl p-6 w-96 shadow-2xl">
        <h3 className="text-white font-semibold text-base mb-2">Save Threshold?</h3>
        <p className="text-gray-400 text-sm mb-4">
          Update <span className="text-white font-medium">{metric}</span> alert threshold from{' '}
          <span className="text-yellow-400 font-mono">{oldVal}%</span> to{' '}
          <span className="text-blue-400 font-mono">{newVal}%</span>?
        </p>
        <p className="text-gray-500 text-xs mb-5">
          This will update the live threshold on the backend. Alerts will fire when {metric} exceeds {newVal}%.
        </p>
        <div className="flex gap-3 justify-end">
          <button onClick={onCancel}
            className="px-4 py-2 rounded-lg text-sm bg-[#21262d] text-gray-400 hover:text-white hover:bg-[#30363d] transition">
            Cancel
          </button>
          <button onClick={onConfirm}
            className="px-4 py-2 rounded-lg text-sm bg-blue-600 hover:bg-blue-700 text-white font-medium transition">
            Save Threshold
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Threshold input row ───────────────────────────────────────────────────────
function ThresholdRow({ label, metric, value, savedValue, onSave }) {
  const [editing, setEditing]   = useState(false)
  const [input, setInput]       = useState(String(value))
  const [showPopup, setShowPopup] = useState(false)
  const [pendingVal, setPendingVal] = useState(null)

  const startEdit = () => {
    setInput(String(value))
    setEditing(true)
  }

  const cancelEdit = () => {
    setEditing(false)
    setInput(String(value))
  }

  const requestSave = () => {
    const num = parseFloat(input)
    if (isNaN(num) || num < 1 || num > 99) return
    setPendingVal(num)
    setShowPopup(true)
    setEditing(false)
  }

  const confirmSave = () => {
    onSave(pendingVal)
    setShowPopup(false)
  }

  const cancelSave = () => {
    setInput(String(value))
    setShowPopup(false)
  }

  const changed = parseFloat(input) !== value

  return (
    <>
      {showPopup && (
        <SavePopup
          metric={label}
          oldVal={savedValue}
          newVal={pendingVal}
          onConfirm={confirmSave}
          onCancel={cancelSave}
        />
      )}
      <div className="flex items-center justify-between p-3 bg-[#0d1117] rounded-lg border border-[#30363d]">
        <div className="flex items-center gap-2">
          <span className="text-sm text-gray-300 w-16">{label}</span>
          <span className="text-xs text-gray-600">threshold</span>
        </div>
        <div className="flex items-center gap-2">
          {editing ? (
            <>
              <input
                type="number"
                min="1" max="99"
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter') requestSave(); if (e.key === 'Escape') cancelEdit() }}
                className="w-20 bg-[#21262d] border border-blue-500 rounded px-2 py-1 text-white text-sm font-mono text-center focus:outline-none"
                autoFocus
              />
              <span className="text-gray-500 text-sm">%</span>
              <button onClick={requestSave} disabled={!changed}
                className={`p-1.5 rounded transition ${changed ? 'text-green-400 hover:bg-green-500/20' : 'text-gray-600 cursor-not-allowed'}`}>
                <Check size={14} />
              </button>
              <button onClick={cancelEdit}
                className="p-1.5 rounded text-gray-500 hover:text-red-400 hover:bg-red-500/20 transition">
                <X size={14} />
              </button>
            </>
          ) : (
            <>
              <span className="text-white font-mono font-bold text-lg w-16 text-right">{value}%</span>
              <button onClick={startEdit}
                className="p-1.5 rounded text-gray-500 hover:text-blue-400 hover:bg-blue-500/20 transition"
                title={`Edit ${label} threshold`}>
                <Pencil size={13} />
              </button>
            </>
          )}
        </div>
      </div>
    </>
  )
}

// ── Gauge card ────────────────────────────────────────────────────────────────
function GaugeCard({ label, value, threshold, icon: Icon }) {
  const pct  = Math.min(value, 100)
  const over = value >= threshold
  const warn = pct > threshold * 0.8 && !over
  return (
    <div className={`p-4 rounded-xl border transition-all
      ${over ? 'border-red-500/50 bg-red-500/5' : 'border-[#30363d] bg-[#161b22]'}`}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2 text-gray-400">
          <Icon size={16} />
          <span className="text-sm">{label}</span>
        </div>
        <span className={`text-2xl font-bold ${
          over ? 'text-red-400' : warn ? 'text-yellow-400' : 'text-green-400'
        }`}>{value?.toFixed(1)}%</span>
      </div>
      <div className="h-2 bg-[#30363d] rounded-full overflow-hidden">
        <div className={`h-full rounded-full transition-all duration-500
          ${over ? 'bg-red-400' : warn ? 'bg-yellow-400' : 'bg-green-400'}`}
          style={{ width: `${pct}%` }} />
      </div>
      <div className="flex justify-between text-xs text-gray-500 mt-1">
        <span>0%</span>
        <span className="text-gray-400">Threshold: {threshold}%</span>
        <span>100%</span>
      </div>
      {over && (
        <div className="mt-2 text-xs text-red-400 flex items-center gap-1">
          ⚠ Above threshold — check processes
        </div>
      )}
    </div>
  )
}

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-[#1c2128] border border-[#30363d] rounded-lg p-2 text-xs">
      <div className="text-gray-400 mb-1">{label}</div>
      {payload.map((p, i) => (
        <div key={i} style={{ color: p.color }}>{p.name}: {p.value?.toFixed(1)}%</div>
      ))}
    </div>
  )
}

// ── Main ──────────────────────────────────────────────────────────────────────
export default function HealthTab({ liveData }) {
  const [metrics,       setMetrics]       = useState([])
  const [cpuThreshold,  setCpuThreshold]  = useState(80)
  const [ramThreshold,  setRamThreshold]  = useState(85)
  const [diskThreshold, setDiskThreshold] = useState(90)
  const [savedCpu,      setSavedCpu]      = useState(80)
  const [savedRam,      setSavedRam]      = useState(85)
  const [savedDisk,     setSavedDisk]     = useState(90)
  const [saveMsg,       setSaveMsg]       = useState('')

  // Load current thresholds from backend on mount
  useEffect(() => {
    api.getThresholds().then(r => {
      if (r?.data) {
        setCpuThreshold(r.data.cpu);   setSavedCpu(r.data.cpu)
        setRamThreshold(r.data.ram);   setSavedRam(r.data.ram)
        setDiskThreshold(r.data.disk); setSavedDisk(r.data.disk)
      }
    }).catch(() => {})
  }, [])

  const fetchMetrics = () =>
    api.metrics(60).then(r => {
      const raw = r.data.metrics || []
      setMetrics(raw.map(m => ({ ...m, time: m.timestamp?.slice(11, 19) || '' })))
    })

  useEffect(() => {
    fetchMetrics()
    const t = setInterval(fetchMetrics, 5000)
    return () => clearInterval(t)
  }, [])

  useEffect(() => {
    if (liveData.latestMetrics) {
      const m = liveData.latestMetrics
      setMetrics(prev => [...prev, { ...m, time: m.timestamp?.slice(11,19)||'' }].slice(-60))
    }
  }, [liveData.latestMetrics])

  const saveThreshold = async (metric, value, setter, setSaved) => {
    setter(value)
    setSaved(value)
    try {
      await api.setThresholds({
        cpu:  metric === 'CPU'  ? value : cpuThreshold,
        ram:  metric === 'RAM'  ? value : ramThreshold,
        disk: metric === 'Disk' ? value : diskThreshold,
      })
      setSaveMsg(`${metric} threshold saved as ${value}%`)
      setTimeout(() => setSaveMsg(''), 3000)
    } catch {
      setSaveMsg('Failed to save — backend may be unreachable')
      setTimeout(() => setSaveMsg(''), 3000)
    }
  }

  const latest = metrics[metrics.length - 1] || {}

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <h1 className="text-xl font-bold text-white">CPU / RAM Health</h1>
        {saveMsg && (
          <span className="text-xs px-3 py-1 bg-green-500/20 text-green-400 rounded-full">
            ✓ {saveMsg}
          </span>
        )}
      </div>
      <p className="text-sm text-gray-400 mb-6">Real-time EC2 server resource monitoring</p>

      {/* Gauge cards */}
      <div className="grid grid-cols-2 gap-4 mb-6">
        <GaugeCard label="CPU"  value={latest.cpu_percent||0}  threshold={cpuThreshold}  icon={Cpu} />
        <GaugeCard label="RAM"  value={latest.ram_percent||0}  threshold={ramThreshold}  icon={MemoryStick} />
        <GaugeCard label="Disk" value={latest.disk_percent||0} threshold={diskThreshold} icon={HardDrive} />
        <div className="p-4 rounded-xl border border-[#30363d] bg-[#161b22]">
          <div className="flex items-center gap-2 text-gray-400 mb-3">
            <Wifi size={16} />
            <span className="text-sm">Network</span>
          </div>
          <div className="grid grid-cols-2 gap-3 text-center">
            <div>
              <div className="text-xl font-bold text-blue-400">{latest.net_sent_mb?.toFixed(1)||0}</div>
              <div className="text-xs text-gray-500">MB Sent</div>
            </div>
            <div>
              <div className="text-xl font-bold text-green-400">{latest.net_recv_mb?.toFixed(1)||0}</div>
              <div className="text-xs text-gray-500">MB Recv</div>
            </div>
          </div>
        </div>
      </div>

      {/* Threshold controls */}
      <div className="bg-[#161b22] border border-[#30363d] rounded-xl p-4 mb-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold text-white">Alert Thresholds</h2>
          <span className="text-xs text-gray-500">Click ✏ to edit, ✓ to save</span>
        </div>
        <div className="grid grid-cols-3 gap-3">
          <ThresholdRow
            label="CPU" metric="CPU"
            value={cpuThreshold} savedValue={savedCpu}
            onSave={v => saveThreshold('CPU', v, setCpuThreshold, setSavedCpu)}
          />
          <ThresholdRow
            label="RAM" metric="RAM"
            value={ramThreshold} savedValue={savedRam}
            onSave={v => saveThreshold('RAM', v, setRamThreshold, setSavedRam)}
          />
          <ThresholdRow
            label="Disk" metric="Disk"
            value={diskThreshold} savedValue={savedDisk}
            onSave={v => saveThreshold('Disk', v, setDiskThreshold, setSavedDisk)}
          />
        </div>
      </div>

      {/* CPU + RAM chart */}
      <div className="bg-[#161b22] border border-[#30363d] rounded-xl p-4 mb-4">
        <h2 className="text-sm font-semibold text-white mb-4">CPU & RAM Over Time</h2>
        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={metrics}>
            <CartesianGrid strokeDasharray="3 3" stroke="#21262d" />
            <XAxis dataKey="time" tick={{ fill:'#6e7681', fontSize:11 }} interval="preserveStartEnd" />
            <YAxis domain={[0,100]} tick={{ fill:'#6e7681', fontSize:11 }} />
            <Tooltip content={<CustomTooltip />} />
            <ReferenceLine y={cpuThreshold} stroke="#ef4444" strokeDasharray="4 4"
              label={{ value:`CPU ${cpuThreshold}%`, fill:'#ef4444', fontSize:10 }} />
            <ReferenceLine y={ramThreshold} stroke="#3b82f6" strokeDasharray="4 4"
              label={{ value:`RAM ${ramThreshold}%`, fill:'#3b82f6', fontSize:10 }} />
            <Line type="monotone" dataKey="cpu_percent" name="CPU %" stroke="#ef4444" strokeWidth={2} dot={false} />
            <Line type="monotone" dataKey="ram_percent" name="RAM %" stroke="#3b82f6" strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Disk chart */}
      <div className="bg-[#161b22] border border-[#30363d] rounded-xl p-4">
        <h2 className="text-sm font-semibold text-white mb-4">Disk Usage</h2>
        <ResponsiveContainer width="100%" height={140}>
          <AreaChart data={metrics}>
            <CartesianGrid strokeDasharray="3 3" stroke="#21262d" />
            <XAxis dataKey="time" tick={{ fill:'#6e7681', fontSize:11 }} interval="preserveStartEnd" />
            <YAxis domain={[0,100]} tick={{ fill:'#6e7681', fontSize:11 }} />
            <Tooltip content={<CustomTooltip />} />
            <ReferenceLine y={diskThreshold} stroke="#f59e0b" strokeDasharray="4 4" />
            <Area type="monotone" dataKey="disk_percent" name="Disk %" stroke="#f59e0b" fill="#f59e0b20" strokeWidth={2} dot={false} />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
