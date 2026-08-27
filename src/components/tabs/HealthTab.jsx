import { useState, useEffect, useRef } from 'react'
import { api } from '../../api'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine, AreaChart, Area
} from 'recharts'
import { Cpu, MemoryStick, HardDrive, Wifi } from 'lucide-react'

function GaugeCard({ label, value, threshold, color, icon: Icon }) {
  const pct   = Math.min(value, 100)
  const over  = value >= threshold
  return (
    <div className={`p-4 rounded-xl border transition-all
      ${over ? 'border-red-500/50 bg-red-500/5' : 'border-[#30363d] bg-[#161b22]'}`}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2 text-gray-400">
          <Icon size={16} />
          <span className="text-sm">{label}</span>
        </div>
        <span className={`text-2xl font-bold ${
          over ? 'text-red-400' : pct > threshold * 0.8 ? 'text-yellow-400' : 'text-green-400'
        }`}>{value?.toFixed(1)}%</span>
      </div>
      <div className="h-2 bg-[#30363d] rounded-full overflow-hidden">
        <div className={`h-full rounded-full transition-all duration-500
          ${over ? 'bg-red-400' : pct > threshold * 0.8 ? 'bg-yellow-400' : 'bg-green-400'}`}
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

export default function HealthTab({ liveData }) {
  const [metrics,       setMetrics]       = useState([])
  const [cpuThreshold,  setCpuThreshold]  = useState(80)
  const [ramThreshold,  setRamThreshold]  = useState(85)
  const [diskThreshold, setDiskThreshold] = useState(90)

  const fetchMetrics = () =>
    api.metrics(60).then(r => {
      const raw = r.data.metrics || []
      setMetrics(raw.map(m => ({
        ...m,
        time: m.timestamp?.slice(11, 19) || ''
      })))
    })

  useEffect(() => {
    fetchMetrics()
    const t = setInterval(fetchMetrics, 5000)
    return () => clearInterval(t)
  }, [])

  useEffect(() => {
    if (liveData.latestMetrics) {
      const m = liveData.latestMetrics
      setMetrics(prev => {
        const next = [...prev, { ...m, time: m.timestamp?.slice(11,19)||'' }]
        return next.slice(-60)
      })
    }
  }, [liveData.latestMetrics])

  const latest = metrics[metrics.length - 1] || {}

  return (
    <div>
      <h1 className="text-xl font-bold text-white mb-2">CPU / RAM Health</h1>
      <p className="text-sm text-gray-400 mb-6">Real-time EC2 server resource monitoring</p>

      {/* Gauge cards */}
      <div className="grid grid-cols-2 gap-4 mb-6">
        <GaugeCard label="CPU"  value={latest.cpu_percent||0}
          threshold={cpuThreshold}  color="blue"   icon={Cpu} />
        <GaugeCard label="RAM"  value={latest.ram_percent||0}
          threshold={ramThreshold}  color="purple" icon={MemoryStick} />
        <GaugeCard label="Disk" value={latest.disk_percent||0}
          threshold={diskThreshold} color="orange" icon={HardDrive} />
        <div className="p-4 rounded-xl border border-[#30363d] bg-[#161b22]">
          <div className="flex items-center gap-2 text-gray-400 mb-3">
            <Wifi size={16} />
            <span className="text-sm">Network</span>
          </div>
          <div className="grid grid-cols-2 gap-3 text-center">
            <div>
              <div className="text-xl font-bold text-blue-400">
                {latest.net_sent_mb?.toFixed(1) || 0}
              </div>
              <div className="text-xs text-gray-500">MB Sent</div>
            </div>
            <div>
              <div className="text-xl font-bold text-green-400">
                {latest.net_recv_mb?.toFixed(1) || 0}
              </div>
              <div className="text-xs text-gray-500">MB Recv</div>
            </div>
          </div>
        </div>
      </div>

      {/* Threshold controls */}
      <div className="bg-[#161b22] border border-[#30363d] rounded-xl p-4 mb-6">
        <h2 className="text-sm font-semibold text-white mb-4">Alert Thresholds</h2>
        <div className="grid grid-cols-3 gap-6">
          {[
            { label: 'CPU %',  val: cpuThreshold,  set: setCpuThreshold  },
            { label: 'RAM %',  val: ramThreshold,  set: setRamThreshold  },
            { label: 'Disk %', val: diskThreshold, set: setDiskThreshold },
          ].map(({ label, val, set }) => (
            <div key={label}>
              <div className="flex justify-between text-sm mb-2">
                <span className="text-gray-400">{label}</span>
                <span className="text-white font-bold">{val}%</span>
              </div>
              <input type="range" min="50" max="99" value={val}
                onChange={e => set(Number(e.target.value))}
                className="w-full accent-blue-400" />
            </div>
          ))}
        </div>
      </div>

      {/* CPU + RAM chart */}
      <div className="bg-[#161b22] border border-[#30363d] rounded-xl p-4 mb-4">
        <h2 className="text-sm font-semibold text-white mb-4">CPU & RAM Over Time</h2>
        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={metrics}>
            <CartesianGrid strokeDasharray="3 3" stroke="#21262d" />
            <XAxis dataKey="time" tick={{ fill:'#6e7681', fontSize:11 }}
              interval="preserveStartEnd" />
            <YAxis domain={[0,100]} tick={{ fill:'#6e7681', fontSize:11 }} />
            <Tooltip content={<CustomTooltip />} />
            <ReferenceLine y={cpuThreshold} stroke="#ef4444" strokeDasharray="4 4"
              label={{ value:`CPU ${cpuThreshold}%`, fill:'#ef4444', fontSize:10 }} />
            <ReferenceLine y={ramThreshold} stroke="#3b82f6" strokeDasharray="4 4"
              label={{ value:`RAM ${ramThreshold}%`, fill:'#3b82f6', fontSize:10 }} />
            <Line type="monotone" dataKey="cpu_percent" name="CPU %"
              stroke="#ef4444" strokeWidth={2} dot={false} />
            <Line type="monotone" dataKey="ram_percent" name="RAM %"
              stroke="#3b82f6" strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Disk chart */}
      <div className="bg-[#161b22] border border-[#30363d] rounded-xl p-4">
        <h2 className="text-sm font-semibold text-white mb-4">Disk Usage</h2>
        <ResponsiveContainer width="100%" height={140}>
          <AreaChart data={metrics}>
            <CartesianGrid strokeDasharray="3 3" stroke="#21262d" />
            <XAxis dataKey="time" tick={{ fill:'#6e7681', fontSize:11 }}
              interval="preserveStartEnd" />
            <YAxis domain={[0,100]} tick={{ fill:'#6e7681', fontSize:11 }} />
            <Tooltip content={<CustomTooltip />} />
            <ReferenceLine y={diskThreshold} stroke="#f59e0b" strokeDasharray="4 4" />
            <Area type="monotone" dataKey="disk_percent" name="Disk %"
              stroke="#f59e0b" fill="#f59e0b20" strokeWidth={2} dot={false} />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
