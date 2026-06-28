import ThoughtProcess from "./ThoughtProcess"
import SourceGraph from "./SourceGraph"
import { User, Bot } from "lucide-react"

function formatTime(ts) {
  if (!ts) return ""
  return new Date(ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
}

function MessageContent({ content }) {
  // Highlight graph triples
  const parts = content.split(/(Graph:.*?(?:\n|$))/g)
  return (
    <div className="text-sm leading-relaxed text-slate-200 whitespace-pre-wrap">
      {parts.map((part, i) =>
        part.startsWith("Graph:") ? (
          <span key={i} className="text-indigo-300 font-mono text-xs
                                    bg-indigo-950/50 px-1 py-0.5 rounded">
            {part}
          </span>
        ) : (
          <span key={i}>{part}</span>
        )
      )}
    </div>
  )
}

export default function MessageBubble({ message, isStreaming }) {
  const isUser = message.role === "user"

  return (
    <div className={`flex gap-3 ${isUser ? "flex-row-reverse" : "flex-row"}`}>
      {/* Avatar */}
      <div className={`shrink-0 w-8 h-8 rounded-full flex items-center justify-center
                       ${isUser ? "bg-red-500" : "bg-indigo-600"}`}>
        {isUser
          ? <User size={16} className="text-white" />
          : <Bot  size={16} className="text-white" />
        }
      </div>

      {/* Bubble */}
      <div className={`flex-1 min-w-0 ${isUser ? "flex flex-col items-end" : ""}`}>
        <div className={isUser ? "chat-bubble-user max-w-[80%]" : "chat-bubble-ai w-full"}>

          {/* AI extras: thought process + source graph */}
          {!isUser && message.steps?.length > 0 && (
            <ThoughtProcess
              steps={message.steps}
              done={!isStreaming}
            />
          )}

          {/* Streaming cursor */}
          {isStreaming && !message.content && (
            <div className="flex gap-1 py-1">
              {[0,1,2].map(i => (
                <span key={i}
                  className="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-bounce"
                  style={{ animationDelay: `${i * 0.15}s` }}
                />
              ))}
            </div>
          )}

          {/* Message content */}
          {message.content && <MessageContent content={message.content} />}

          {/* Source graph (after streaming done) */}
          {!isUser && message.sources?.length > 0 && (
            <SourceGraph query={message.query} sources={message.sources} />
          )}
        </div>

        {/* Timestamp + model */}
        <div className={`flex items-center gap-2 mt-1 px-1
                         ${isUser ? "flex-row-reverse" : "flex-row"}`}>
          <span className="text-xs text-slate-600">{formatTime(message.ts)}</span>
          {message.model && (
            <span className="text-xs text-slate-700">· {message.model.split("/").pop()}</span>
          )}
          {message.complexity && (
            <span className={`text-xs px-1.5 py-0.5 rounded-full
              ${message.complexity === "Complex"
                ? "bg-purple-950 text-purple-400"
                : message.complexity === "Medium"
                ? "bg-amber-950 text-amber-400"
                : "bg-blue-950 text-blue-400"}`}>
              {message.complexity}
            </span>
          )}
        </div>
      </div>
    </div>
  )
}
