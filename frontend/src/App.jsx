import { useState, useEffect, useRef, useCallback } from "react"
import { Send, StopCircle } from "lucide-react"
import Sidebar from "./components/Sidebar"
import MessageBubble from "./components/MessageBubble"
import ModelSelector from "./components/ModelSelector"

const WS_URL  = "ws://localhost:8000/ws/chat"
const API_URL = "http://localhost:8000"
const USER    = "local_user"

function genId() { return crypto.randomUUID() }

export default function App() {
  const [conversations, setConversations] = useState([])
  const [activeId,      setActiveId]      = useState(() => genId())
  const [messages,      setMessages]      = useState([])
  const [input,         setInput]         = useState("")
  const [streaming,     setStreaming]     = useState(false)
  const [models,        setModels]        = useState([])
  const [selectedModel, setSelectedModel] = useState("auto")
  const [turnCount,     setTurnCount]     = useState(0)

  const wsRef      = useRef(null)

  // Guard: ensure input is always a clean string
  useEffect(() => {
    if (typeof input !== "string" || input === "[object Object]") setInput("")
  }, [input])
  const bottomRef  = useRef(null)
  const inputRef   = useRef(null)
  // Refs to avoid stale closures inside WebSocket handlers
  const activeIdRef   = useRef(activeId)
  const turnCountRef  = useRef(turnCount)
  const messagesRef   = useRef(messages)

  useEffect(() => { activeIdRef.current  = activeId  }, [activeId])
  useEffect(() => { turnCountRef.current = turnCount }, [turnCount])
  useEffect(() => { messagesRef.current  = messages  }, [messages])

  // Auto-scroll
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages])

  // Load models
  useEffect(() => {
    fetch(`${API_URL}/models`)
      .then(r => r.json())
      .then(d => setModels(d.models || []))
      .catch(() => setModels([
        { display: "🤖 Auto (Smart Routing)",     id: "auto" },
        { display: "Llama 3.3 70B — Most Capable", id: "llama-3.3-70b-versatile" },
        { display: "Llama 3.1 8B — Fast",          id: "llama-3.1-8b-instant" },
      ]))
  }, [])

  // Load conversation history
  useEffect(() => {
    fetch(`${API_URL}/conversations/${USER}`)
      .then(r => r.json())
      .then(d => setConversations(d.conversations || []))
      .catch(() => {})
  }, [])

  // Save conversation to backend
  const saveConversation = useCallback((msgs, id, count) => {
    if (!msgs.length) return
    const title = msgs.find(m => m.role === "user")?.content?.slice(0, 50) || "Untitled"
    fetch(`${API_URL}/conversations/save`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: id, user_name: USER,
                             title, turn_count: count, messages: msgs }),
    }).catch(() => {})
    setConversations(prev => {
      const rest = prev.filter(c => c.id !== id)
      return [{ id, title, messages: msgs, turn_count: count,
                updated_at: new Date().toISOString() }, ...rest]
    })
  }, [])

  // Send message
  const sendMessage = useCallback(() => {
    const query = String(input || "").trim()
    if (!query || streaming) return
    setInput("")
    setStreaming(true)

    const userMsg = { role: "user", content: query, ts: Date.now() }
    const aiMsg   = { role: "assistant", content: "", steps: [],
                      sources: [], query, ts: Date.now(),
                      model: null, complexity: null }

    setMessages(prev => [...prev, userMsg, aiMsg])

    const ws = new WebSocket(WS_URL)
    wsRef.current = ws

    ws.onopen = () => {
      ws.send(JSON.stringify({
        query,
        thread_id: activeIdRef.current,
        model: selectedModel,
      }))
    }

    ws.onmessage = (e) => {
      let event
      try { event = JSON.parse(e.data) } catch { return }

      if (event.type === "done") {
        ws.close()
        return
      }

      setMessages(prev => {
        if (!prev.length) return prev
        const updated = [...prev]
        const last    = updated[updated.length - 1]
        if (last.role !== "assistant") return prev

        const ai = { ...last }

        if (event.type === "model_selected") {
          ai.model      = event.model
          ai.complexity = event.label
          ai.steps      = [...(ai.steps || []), event]
        } else if (event.type === "tool_call") {
          ai.steps = [...(ai.steps || []), event]
        } else if (event.type === "tool_result") {
          ai.steps = [...(ai.steps || []), event]
          if (event.sources?.length) {
            ai.sources = [...(ai.sources || []), ...event.sources]
          }
        } else if (event.type === "token") {
          ai.content = (ai.content || "") + event.content
        } else if (event.type === "error") {
          ai.content = `⚠️ Error: ${event.message}`
        }

        updated[updated.length - 1] = ai
        return updated
      })
    }

    ws.onclose = () => {
      setStreaming(false)
      wsRef.current = null
      const newCount = turnCountRef.current + 1
      setTurnCount(newCount)
      // Use refs to get latest values — avoids stale closure
      saveConversation(messagesRef.current, activeIdRef.current, newCount)
      inputRef.current?.focus()
    }

    ws.onerror = () => {
      setStreaming(false)
      setMessages(prev => {
        if (!prev.length) return prev
        const updated = [...prev]
        const last    = { ...updated[updated.length - 1] }
        last.content  = "⚠️ Connection error — is the backend running on port 8000?"
        updated[updated.length - 1] = last
        return updated
      })
    }
  }, [input, streaming, selectedModel, saveConversation])

  // New conversation
  const handleNew = useCallback((prefill) => {
    saveConversation(messagesRef.current, activeIdRef.current, turnCountRef.current)
    const newId = genId()
    setActiveId(newId)
    setMessages([])
    setTurnCount(0)
    // Always sanitize — guard against SyntheticEvent or object being passed as prefill
    const safe = typeof prefill === "string" ? prefill : ""
    setInput(safe)
    setTimeout(() => inputRef.current?.focus(), 50)
  }, [saveConversation])

  // Load conversation
  const handleLoad = useCallback((conv) => {
    saveConversation(messagesRef.current, activeIdRef.current, turnCountRef.current)
    setActiveId(conv.id)
    setMessages(conv.messages || [])
    setTurnCount(conv.turn_count || 0)
  }, [saveConversation])

  // Delete one conversation
  const handleDelete = useCallback((id) => {
    fetch(`${API_URL}/conversations/${id}`, { method: "DELETE" }).catch(() => {})
    setConversations(prev => prev.filter(c => c.id !== id))
    if (id === activeIdRef.current) handleNew()
  }, [handleNew])

  // Delete all conversations
  const handleDeleteAll = useCallback(async () => {
    const ids = conversations.map(c => c.id)
    await Promise.all(ids.map(id =>
      fetch(`${API_URL}/conversations/${id}`, { method: "DELETE" }).catch(() => {})
    ))
    setConversations([])
    handleNew()
  }, [conversations, handleNew])

  // Stop streaming
  const stopStreaming = () => {
    wsRef.current?.close()
    setStreaming(false)
  }

  // Keyboard
  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage() }
  }

  return (
    <div className="flex h-screen overflow-hidden bg-[#0e1117]">
      <Sidebar
        conversations={conversations}
        activeId={activeId}
        onNew={handleNew}
        onLoad={handleLoad}
        onDelete={handleDelete}
        onDeleteAll={handleDeleteAll}
      />

      <div className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <header className="shrink-0 px-6 py-3 border-b border-slate-800
                           flex items-center justify-between bg-[#0e1117]">
          <div>
            <h2 className="text-base font-semibold text-slate-100">
              Supply Chain Graph RAG
            </h2>
            <p className="text-xs text-slate-600">
              Neo4j + Weaviate · Groq · LangGraph · Turn {turnCount}
            </p>
          </div>
          {streaming && (
            <span className="flex items-center gap-1.5 text-xs text-indigo-400">
              <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-pulse" />
              Generating...
            </span>
          )}
        </header>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-6 py-6 space-y-6">
          {messages.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full text-center">
              <div className="text-4xl mb-4">🕸️</div>
              <h3 className="text-lg font-semibold text-slate-300 mb-2">
                Supply Chain Graph RAG
              </h3>
              <p className="text-sm text-slate-500 max-w-sm">
                Combining Neo4j knowledge graph with Weaviate vector search
                to answer complex supply chain questions.
              </p>
            </div>
          )}
          {messages.map((msg, i) => (
            <MessageBubble
              key={i}
              message={msg}
              isStreaming={
                streaming &&
                i === messages.length - 1 &&
                msg.role === "assistant"
              }
            />
          ))}
          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <div className="shrink-0 px-6 py-4 border-t border-slate-800 bg-[#0e1117]">
          <div className="flex items-center gap-2 mb-2">
            <ModelSelector
              models={models}
              selected={selectedModel}
              onSelect={setSelectedModel}
            />
            {selectedModel === "auto" && (
              <span className="text-xs text-slate-700">· complexity auto-detected</span>
            )}
          </div>
          <div className="flex items-end gap-3">
            <textarea
              ref={inputRef}
              value={input}
              onChange={e => setInput(String(e.target.value || ""))}
              onKeyDown={handleKeyDown}
              placeholder="Ask about supply chain risks, suppliers, logistics..."
              rows={1}
              disabled={streaming}
              className="flex-1 resize-none bg-slate-800 border border-slate-700
                         rounded-xl px-4 py-3 text-sm text-slate-200
                         placeholder:text-slate-600
                         focus:outline-none focus:border-indigo-500
                         focus:ring-1 focus:ring-indigo-500/50
                         transition-colors duration-150 max-h-40 overflow-y-auto"
              style={{ minHeight: 48 }}
              onInput={e => {
                e.target.style.height = "auto"
                e.target.style.height = Math.min(e.target.scrollHeight, 160) + "px"
              }}
            />
            <button
              onClick={streaming ? stopStreaming : sendMessage}
              disabled={!streaming && !input.trim()}
              className={`shrink-0 w-11 h-11 rounded-xl flex items-center justify-center
                          transition-all duration-150
                          ${streaming
                            ? "bg-red-600 hover:bg-red-500 text-white"
                            : String(input || "").trim()
                            ? "bg-indigo-600 hover:bg-indigo-500 text-white"
                            : "bg-slate-800 text-slate-600 cursor-not-allowed"}`}
            >
              {streaming ? <StopCircle size={18} /> : <Send size={18} />}
            </button>
          </div>
          <p className="text-xs text-slate-700 mt-1.5 px-1">
            Enter to send · Shift+Enter for new line
          </p>
        </div>
      </div>
    </div>
  )
}