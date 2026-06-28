import { useState, useRef, useEffect } from "react"
import { ChevronDown, Zap, Brain, Cpu, Wind } from "lucide-react"

const MODEL_ICONS = {
  "auto":                                      { icon: Zap,   color: "text-indigo-400" },
  "llama-3.3-70b-versatile":                   { icon: Brain, color: "text-purple-400" },
  "llama-3.1-8b-instant":                      { icon: Wind,  color: "text-blue-400"   },
  "meta-llama/llama-4-scout-17b-16e-instruct": { icon: Cpu,   color: "text-green-400"  },
  "llama-3.1-70b-versatile":                   { icon: Brain, color: "text-amber-400"  },
}

export default function ModelSelector({ models, selected, onSelect }) {
  const [open, setOpen]   = useState(false)
  const ref               = useRef(null)

  useEffect(() => {
    const handler = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false) }
    document.addEventListener("mousedown", handler)
    return () => document.removeEventListener("mousedown", handler)
  }, [])

  const current = models.find(m => m.id === selected) || models[0]
  const { icon: Icon, color } = MODEL_ICONS[current?.id] || { icon: Zap, color: "text-slate-400" }

  return (
    <div ref={ref} className="relative">
      {/* Trigger */}
      <button
        onClick={() => setOpen(o => !o)}
        className="flex items-center gap-2 px-3 py-1.5 rounded-lg
                   bg-slate-800 border border-slate-700 hover:border-slate-500
                   text-sm text-slate-300 transition-all duration-150"
      >
        <Icon size={14} className={color} />
        <span className="max-w-[180px] truncate">{current?.display || "Select model"}</span>
        <ChevronDown size={14} className={`text-slate-500 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>

      {/* Dropdown */}
      {open && (
        <div className="absolute bottom-full mb-2 left-0 w-72
                        bg-slate-900 border border-slate-700 rounded-xl shadow-2xl
                        overflow-hidden z-[9999]">
          <div className="px-3 py-2 border-b border-slate-800">
            <p className="text-xs text-slate-500 font-medium uppercase tracking-wider">Select Model</p>
          </div>
          {models.map(m => {
            const { icon: MIcon, color: mc } = MODEL_ICONS[m.id] || { icon: Cpu, color: "text-slate-400" }
            const isActive = m.id === selected
            return (
              <button
                key={m.id}
                onClick={() => { onSelect(m.id); setOpen(false) }}
                className={`w-full flex items-center gap-3 px-4 py-3 text-left
                            hover:bg-slate-800 transition-colors duration-100
                            ${isActive ? "bg-slate-800/80" : ""}`}
              >
                <MIcon size={16} className={mc} />
                <div className="flex-1 min-w-0">
                  <p className={`text-sm font-medium truncate ${isActive ? "text-white" : "text-slate-300"}`}>
                    {m.display}
                  </p>
                  <p className="text-xs text-slate-500 truncate">{m.id}</p>
                </div>
                {isActive && (
                  <span className="w-2 h-2 rounded-full bg-indigo-500 shrink-0" />
                )}
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}
