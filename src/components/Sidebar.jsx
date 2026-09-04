import { Activity, Cpu, Bell, Brain, Server, Terminal } from 'lucide-react'

const ICONS = {
  'applications': Server,
  'ai-monitor':   Brain,
  'health':       Cpu,
  'alerts':       Bell,
  'live-logs':    Terminal,
}

export default function Sidebar({ tabs, activeTab, setActiveTab, liveData }) {
  const hasAlert = liveData.latestAlert?.severity === 'CRITICAL'

  return (
    <aside className="w-56 bg-[#161b22] border-r border-[#30363d] flex flex-col">
      {/* Logo */}
      <div className="p-4 border-b border-[#30363d]">
        <div className="flex items-center gap-2">
          <Activity className="text-blue-400" size={20} />
          <span className="font-bold text-white text-sm">AI Monitor</span>
        </div>
        <div className="flex items-center gap-1 mt-1">
          <span className="pulse-dot w-2 h-2 rounded-full bg-green-400 inline-block" />
          <span className="text-xs text-gray-400">Live</span>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 p-2 space-y-1">
        {tabs.map(tab => {
          const Icon    = ICONS[tab.id] || Activity
          const isActive = activeTab === tab.id
          const showBadge = tab.id === 'alerts' && hasAlert
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-all
                ${isActive
                  ? 'bg-[#1f6feb] text-white'
                  : 'text-gray-400 hover:text-white hover:bg-[#21262d]'}`}
            >
              <Icon size={16} />
              <span className="flex-1 text-left">{tab.label}</span>
              {showBadge && (
                <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
              )}
            </button>
          )
        })}
      </nav>

      {/* Footer */}
      <div className="p-3 border-t border-[#30363d] text-xs text-gray-500">
        EC2 Server Monitor
      </div>
    </aside>
  )
}
