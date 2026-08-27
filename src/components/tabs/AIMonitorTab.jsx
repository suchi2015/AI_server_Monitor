import { useState, useEffect } from 'react'
import { api } from '../../api'
import { Brain, ChevronRight, X, Lightbulb, AlertCircle } from 'lucide-react'

function SeverityDot({ sev }) {
  const colors = { CRITICAL:'bg-red-500', ERROR:'bg-red-400',
                   WARNING:'bg-yellow-400', INFO:'bg-green-400', FATAL:'bg-purple-500' }
  return <span className={`w-2 h-2 rounded-full inline-block ${colors[sev]||'bg-gray-400'}`} />
}

export default function AIMonitorTab({ liveData }) {
  const [anomalies,  setAnomalies]  = useState([])
  const [incidents,  setIncidents]  = useState([])
  const [selected,   setSelected]   = useState(null)
  const [panel,      setPanel]      = useState(false)

  const fetchData = () => {
    api.anomalies(40).then(r  => setAnomalies(r.data.anomalies || []))
    api.incidents(20).then(r  => setIncidents(r.data.incidents || []))
  }

  useEffect(() => {
    fetchData()
    const t = setInterval(fetchData, 6000)
    return () => clearInterval(t)
  }, [])

  useEffect(() => {
    if (liveData.latestIncident) {
      fetchData()
      setSelected(liveData.latestIncident)
      setPanel(true)
    }
  }, [liveData.latestIncident])

  const openPanel = (item) => { setSelected(item); setPanel(true) }

  return (
    <div className="flex gap-4 h-full">
      {/* Main content */}
      <div className="flex-1">
        <div className="flex items-center gap-2 mb-6">
          <Brain className="text-blue-400" size={20} />
          <h1 className="text-xl font-bold text-white">AI Monitor</h1>
          <span className="ml-2 text-xs px-2 py-0.5 bg-blue-500/20 text-blue-400 rounded-full">
            {anomalies.length} anomalies
          </span>
        </div>

        {/* Incidents */}
        {incidents.length > 0 && (
          <div className="mb-6">
            <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-3">
              Active Incidents
            </h2>
            <div className="space-y-2">
              {incidents.filter(i => i.status === 'open').map(inc => (
                <div key={inc.incident_id}
                  onClick={() => openPanel(inc)}
                  className="flex items-center justify-between p-3 bg-red-500/5 border border-red-500/30
                             rounded-lg cursor-pointer hover:bg-red-500/10 transition">
                  <div className="flex items-center gap-3">
                    <AlertCircle size={16} className="text-red-400" />
                    <div>
                      <div className="text-sm font-medium text-white">{inc.incident_id}</div>
                      <div className="text-xs text-gray-400">{inc.summary?.slice(0, 80)}</div>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-xs text-gray-400">{inc.affected_apps?.join(', ')}</span>
                    <span className={`text-xs px-2 py-0.5 rounded-full
                      ${inc.severity === 'CRITICAL' ? 'bg-red-500/20 text-red-400' :
                        inc.severity === 'HIGH'     ? 'bg-orange-500/20 text-orange-400' :
                        'bg-yellow-500/20 text-yellow-400'}`}>
                      {inc.severity}
                    </span>
                    <ChevronRight size={14} className="text-gray-500" />
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Anomaly list */}
        <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-3">
          Detected Errors & Anomalies
        </h2>
        <div className="space-y-2">
          {anomalies.length === 0 ? (
            <div className="text-center text-gray-500 py-12">
              ✅ No anomalies detected. All systems normal.
            </div>
          ) : anomalies.map((a, i) => (
            <div key={i}
              onClick={() => openPanel(a)}
              className="flex items-start gap-3 p-3 bg-[#161b22] border border-[#30363d]
                         rounded-lg cursor-pointer hover:border-[#58a6ff] transition group">
              <SeverityDot sev={a.severity} />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-xs font-semibold text-blue-400">{a.app}</span>
                  <span className="text-xs text-gray-500">{a.timestamp?.slice(0,19)}</span>
                  <span className="text-xs px-1.5 py-0.5 bg-gray-700 rounded text-gray-300">
                    score: {(a.anomaly_score||0).toFixed(2)}
                  </span>
                </div>
                <div className="text-sm text-gray-200 truncate">{a.message?.slice(0,100)}</div>
                {a.explanation && (
                  <div className="text-xs text-gray-400 mt-0.5 truncate">{a.explanation?.slice(0,100)}</div>
                )}
              </div>
              <ChevronRight size={14} className="text-gray-500 group-hover:text-blue-400 shrink-0 mt-1" />
            </div>
          ))}
        </div>
      </div>

      {/* Side panel */}
      {panel && selected && (
        <div className="w-96 bg-[#161b22] border border-[#30363d] rounded-xl p-5 overflow-y-auto shrink-0">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-white flex items-center gap-2">
              <Lightbulb size={16} className="text-yellow-400" />
              Analysis
            </h3>
            <button onClick={() => setPanel(false)}
              className="text-gray-500 hover:text-white transition">
              <X size={16} />
            </button>
          </div>

          {/* App + Severity */}
          <div className="flex items-center gap-2 mb-4">
            <span className="text-xs px-2 py-1 bg-blue-500/20 text-blue-400 rounded">
              {selected.app || selected.affected_apps?.join(', ')}
            </span>
            <span className={`text-xs px-2 py-1 rounded
              ${selected.severity === 'CRITICAL' || selected.severity === 'HIGH'
                ? 'bg-red-500/20 text-red-400'
                : 'bg-yellow-500/20 text-yellow-400'}`}>
              {selected.severity}
            </span>
          </div>

          {/* Raw log */}
          {selected.raw && (
            <>
              <div className="text-xs text-gray-400 uppercase tracking-wide mb-2">Log Entry</div>
              <div className="bg-[#0d1117] rounded-lg p-3 text-xs font-mono text-gray-300 mb-4 break-all">
                {selected.raw}
              </div>
            </>
          )}

          {/* Summary / Explanation */}
          {(selected.explanation || selected.summary) && (
            <>
              <div className="text-xs text-gray-400 uppercase tracking-wide mb-2">AI Explanation</div>
              <div className="bg-blue-500/10 border border-blue-500/20 rounded-lg p-3 text-sm text-blue-200 mb-4">
                {selected.explanation || selected.summary}
              </div>
            </>
          )}

          {/* Root cause */}
          {selected.root_cause && (
            <>
              <div className="text-xs text-gray-400 uppercase tracking-wide mb-2">Root Cause</div>
              <div className="bg-orange-500/10 border border-orange-500/20 rounded-lg p-3 text-sm text-orange-200 mb-4">
                {selected.root_cause}
              </div>
            </>
          )}

          {/* Fix recommendations */}
          {selected.recommendation?.length > 0 && (
            <>
              <div className="text-xs text-gray-400 uppercase tracking-wide mb-2">
                🛠 Fix Steps
              </div>
              <div className="space-y-2">
                {selected.recommendation.map((step, i) => (
                  <div key={i} className="flex items-start gap-2 text-sm text-gray-300">
                    <span className="text-blue-400 shrink-0 font-mono text-xs mt-0.5">
                      {String(i+1).padStart(2,'0')}
                    </span>
                    <span>{step.replace(/^\d+\.\s*/, '')}</span>
                  </div>
                ))}
              </div>
            </>
          )}

          {/* Resolve button for incidents */}
          {selected.incident_id && selected.status === 'open' && (
            <button
              onClick={() => {
                api.resolveIncident(selected.incident_id).then(() => {
                  setPanel(false)
                  fetchData()
                })
              }}
              className="mt-6 w-full py-2 bg-green-600 hover:bg-green-700 text-white
                         rounded-lg text-sm font-medium transition">
              ✅ Mark as Resolved
            </button>
          )}
        </div>
      )}
    </div>
  )
}
