import { Plus, Trash2, MessageSquare, Clock, Trash } from "lucide-react"

export default function Sidebar({ conversations = [], activeId, onNew, onLoad, onDelete, onDeleteAll }) {
  const sorted = [...conversations].sort(
    (a, b) => new Date(b.updated_at) - new Date(a.updated_at)
  )

  return (
    <aside className="w-64 shrink-0 flex flex-col bg-[#161b27] border-r border-slate-800 h-screen">
      {/* Logo */}
      <div className="px-4 py-4 border-b border-slate-800">
        <h1 className="text-base font-bold text-slate-100">🕸️ SCM Graph RAG</h1>
        <p className="text-xs text-slate-500 mt-0.5">Groq · Weaviate · Neo4j</p>
      </div>

      {/* New conversation */}
      <div className="px-3 py-3 border-b border-slate-800">
        <button
          onClick={() => onNew()}
          className="w-full flex items-center justify-center gap-2
                     bg-indigo-600 hover:bg-indigo-500 text-white
                     text-sm font-medium py-2 rounded-lg transition-colors"
        >
          <Plus size={16} />
          New Conversation
        </button>
      </div>

      {/* History header + Delete All */}
      <div className="flex items-center justify-between px-3 pt-3 pb-1">
        <p className="text-xs font-medium text-slate-600 uppercase tracking-wider">
          History
        </p>
        {sorted.length > 0 && (
          <button
            onClick={onDeleteAll}
            className="flex items-center gap-1 text-xs text-slate-600
                       hover:text-red-400 transition-colors px-1.5 py-0.5
                       rounded hover:bg-red-950/40"
            title="Delete all conversations"
          >
            <Trash size={11} />
            Delete all
          </button>
        )}
      </div>

      {/* Conversation list */}
      <div className="flex-1 overflow-y-auto px-2 pb-2">
        {sorted.length === 0 && (
          <p className="px-2 py-6 text-xs text-slate-600 text-center">
            No conversations yet
          </p>
        )}
        {sorted.map(conv => (
          <div
            key={conv.id}
            className={`flex items-center gap-2 px-3 py-2.5 rounded-lg cursor-pointer
                        mb-0.5 transition-colors duration-100
                        ${conv.id === activeId
                          ? "bg-slate-700/60 text-slate-200"
                          : "text-slate-400 hover:bg-slate-800 hover:text-slate-300"}`}
            onClick={() => onLoad(conv)}
          >
            <MessageSquare size={14} className="shrink-0 opacity-60" />
            <div className="flex-1 min-w-0">
              <p className="text-xs font-medium truncate">{conv.title || "Untitled"}</p>
              <div className="flex items-center gap-1 mt-0.5">
                <Clock size={10} className="opacity-40" />
                <span className="text-[10px] text-slate-600">
                  {conv.turn_count} turn{conv.turn_count !== 1 ? "s" : ""}
                </span>
              </div>
            </div>
            {/* Delete button — always visible */}
            <button
              onClick={e => { e.stopPropagation(); onDelete(conv.id) }}
              className="shrink-0 p-1 rounded text-slate-600
                         hover:text-red-400 hover:bg-red-950/40
                         transition-colors duration-100"
              title="Delete conversation"
            >
              <Trash2 size={13} />
            </button>
          </div>
        ))}
      </div>

      {/* Try these */}
      <div className="px-3 py-3 border-t border-slate-800">
        <p className="text-xs font-medium text-slate-600 mb-2">Try these</p>
        {[
          "What are the main SCM risks for electronics?",
          "Which suppliers are exposed to port risks?",
          "How does JIT inventory affect supplier risk?",
          "Explain demand forecasting in supply chains.",
          "What technologies optimize supply chain planning?",
        ].map(q => (
          <button
            key={q}
            onClick={() => onNew(q)}
            className="w-full text-left text-xs text-slate-500 hover:text-slate-300
                       py-1.5 px-2 rounded hover:bg-slate-800 transition-colors truncate"
          >
            {q}
          </button>
        ))}
      </div>

      <div className="px-4 py-2 border-t border-slate-800">
        <p className="text-[10px] text-slate-700">© SCM Graph RAG · React Build</p>
      </div>
    </aside>
  )
}