import { useState } from "react"
import { ChevronDown, ChevronRight, Search, GitBranch, CheckCircle, Cpu } from "lucide-react"

function StepIcon({ type, tool }) {
  if (type === "model_selected") return <Cpu size={14} className="text-indigo-400" />
  if (type === "tool_call") {
    return tool?.includes("weaviate")
      ? <Search size={14} className="text-blue-400" />
      : <GitBranch size={14} className="text-purple-400" />
  }
  if (type === "tool_result") return <CheckCircle size={14} className="text-green-400" />
  return null
}

function StepText({ step }) {
  if (step.type === "model_selected") {
    return (
      <span>
        <span className="text-indigo-300 font-medium">[{step.label}]</span>
        {" "}Auto-selected{" "}
        <code className="text-xs bg-slate-800 px-1.5 py-0.5 rounded text-indigo-300">{step.model}</code>
        {" — "}<span className="text-slate-400">{step.reason}</span>
      </span>
    )
  }
  if (step.type === "tool_call") {
    const label = step.tool?.includes("weaviate") ? "Searching documents" : "Querying knowledge graph"
    return (
      <span>
        <span className="text-slate-300">{label}</span>
        {step.query && (
          <span className="text-slate-500 italic"> — {step.query.slice(0, 60)}{step.query.length > 60 ? "…" : ""}</span>
        )}
      </span>
    )
  }
  if (step.type === "tool_result") {
    const label = step.tool?.includes("weaviate") ? "Document search complete" : "Graph traversal complete"
    const sources = step.sources?.map(s => s.file).join(", ")
    return (
      <span>
        <span className="text-green-400">{label}</span>
        {sources && <span className="text-slate-500"> — {sources}</span>}
      </span>
    )
  }
  return null
}

export default function ThoughtProcess({ steps, done }) {
  const [expanded, setExpanded] = useState(true)

  if (!steps?.length) return null

  return (
    <div className="mb-3 rounded-xl border border-slate-800 overflow-hidden">
      {/* Header */}
      <button
        onClick={() => setExpanded(e => !e)}
        className="w-full flex items-center gap-2 px-4 py-2.5
                   bg-slate-900/80 hover:bg-slate-800/60
                   text-sm text-slate-400 transition-colors duration-100"
      >
        {expanded
          ? <ChevronDown size={14} />
          : <ChevronRight size={14} />
        }
        <span className="font-medium">Thought process</span>
        {!done && (
          <span className="ml-auto flex items-center gap-1.5 text-xs text-indigo-400">
            <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-pulse" />
            Thinking...
          </span>
        )}
        {done && (
          <span className="ml-auto text-xs text-slate-600">{steps.length} steps</span>
        )}
      </button>

      {/* Steps */}
      {expanded && (
        <div className="bg-slate-900/40 border-t border-slate-800 divide-y divide-slate-800/50">
          {steps.map((step, i) => (
            <div key={i} className="flex items-start gap-3 px-4 py-2.5">
              <div className="mt-0.5 shrink-0">
                <StepIcon type={step.type} tool={step.tool} />
              </div>
              <p className="text-xs text-slate-400 leading-relaxed">
                <StepText step={step} />
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
