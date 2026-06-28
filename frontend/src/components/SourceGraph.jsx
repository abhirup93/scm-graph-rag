import { useEffect, useRef } from "react"
import cytoscape from "cytoscape"

// No fcose needed — using built-in breadthfirst layout

function scoreColor(score) {
  if (score >= 0.7) return { bg: "#bbf7d0", border: "#16a34a", text: "#14532d" }
  if (score >= 0.4) return { bg: "#fef08a", border: "#ca8a04", text: "#713f12" }
  return { bg: "#bfdbfe", border: "#3b82f6", text: "#1e3a8a" }
}

function docLabel(filename) {
  const m = filename?.match(/(\d{4}\.\d{5})(v\d+)\.pdf/)
  if (m) return `arXiv:${m[1]} · ${m[2].toUpperCase()}`
  return (filename || "").replace(/_/g, " ").replace(".pdf", "").slice(0, 24)
}

export default function SourceGraph({ query, sources }) {
  const containerRef = useRef(null)
  const cyRef        = useRef(null)

  useEffect(() => {
    if (!containerRef.current || !sources?.length) return
    if (cyRef.current) { cyRef.current.destroy(); cyRef.current = null }

    const elements = []

    // Query node
    elements.push({
      data: { id: "query", label: (query || "").slice(0, 38) + ((query || "").length > 38 ? "…" : ""), type: "query" }
    })

    // Group arXiv vs standalone
    const arxivGroups = {}
    const standalone  = []
    for (const src of sources) {
      const m = src.file?.match(/(\d{4}\.\d{5})(v\d+)\.pdf/)
      if (m) {
        if (!arxivGroups[m[1]]) arxivGroups[m[1]] = []
        arxivGroups[m[1]].push({ ...src, _ver: m[2] })
      } else {
        standalone.push(src)
      }
    }

    // arXiv paper nodes
    for (const [aid, versions] of Object.entries(arxivGroups)) {
      const pid = `paper_${aid}`
      elements.push({ data: { id: pid, label: `arXiv:${aid}`, type: "paper" } })
      elements.push({
        data: {
          id: `e_q_${pid}`, source: "query", target: pid,
          label: `${versions.reduce((s, v) => s + (v.chunk_count || 0), 0)} chunks`
        }
      })
      for (const v of versions) {
        const col = scoreColor(v.max_score || 0)
        elements.push({
          data: {
            id: v.file,
            label: `${(v._ver || "").toUpperCase()} · ${v.chunk_count || 0}ch · ${v.avg_score || 0}`,
            type: "version", bg: col.bg, border: col.border, text: col.text
          }
        })
        elements.push({
          data: { id: `e_p_${v.file}`, source: pid, target: v.file, label: "", dashed: true }
        })
      }
    }

    // Standalone nodes
    for (const src of standalone) {
      const col = scoreColor(src.max_score || 0)
      elements.push({
        data: {
          id: src.file,
          label: `${docLabel(src.file)}\n${src.chunk_count || 0}ch · ${src.avg_score || 0}`,
          type: "standalone", bg: col.bg, border: col.border, text: col.text
        }
      })
      elements.push({
        data: { id: `e_q_${src.file}`, source: "query", target: src.file,
                label: `${src.chunk_count || 0} chunks` }
      })
    }

    try {
      cyRef.current = cytoscape({
        container: containerRef.current,
        elements,
        style: [
          {
            selector: "node[type='query']",
            style: {
              "background-color": "#6366f1",
              "border-color": "#4338ca", "border-width": 2,
              "label": "data(label)", "color": "#ffffff",
              "font-size": 11, "text-wrap": "wrap", "text-max-width": 140,
              "text-valign": "center", "text-halign": "center",
              "shape": "round-rectangle", "width": 160, "height": 48, "padding": 8,
            }
          },
          {
            selector: "node[type='paper']",
            style: {
              "background-color": "#1e293b",
              "border-color": "#475569", "border-width": 1.5,
              "label": "data(label)", "color": "#cbd5e1",
              "font-size": 10, "text-wrap": "wrap", "text-max-width": 130,
              "text-valign": "center", "text-halign": "center",
              "shape": "round-rectangle", "width": 150, "height": 40,
            }
          },
          {
            selector: "node[type='version'], node[type='standalone']",
            style: {
              "background-color": "data(bg)",
              "border-color": "data(border)", "border-width": 1.5,
              "label": "data(label)", "color": "data(text)",
              "font-size": 10, "text-wrap": "wrap", "text-max-width": 130,
              "text-valign": "center", "text-halign": "center",
              "shape": "round-rectangle", "width": 150, "height": 44,
            }
          },
          {
            selector: "edge",
            style: {
              "line-color": "#475569",
              "target-arrow-color": "#475569",
              "target-arrow-shape": "triangle",
              "curve-style": "bezier",
              "label": "data(label)",
              "font-size": 9, "color": "#64748b",
              "text-background-color": "#0a0f1a",
              "text-background-opacity": 0.9, "text-background-padding": 2,
              "width": 1.5,
            }
          },
          {
            selector: "edge[?dashed]",
            style: { "line-style": "dashed", "line-color": "#334155" }
          },
        ],
        layout: {
          name: "breadthfirst",   // built-in, no plugin needed
          directed: true,
          roots: "#query",
          padding: 40,
          spacingFactor: 1.8,
          animate: true,
          animationDuration: 500,
          fit: true,
        },
        userZoomingEnabled: true,
        userPanningEnabled: true,
        boxSelectionEnabled: false,
        minZoom: 0.3,
        maxZoom: 3,
      })
    } catch (err) {
      console.error("Cytoscape render error:", err)
    }

    return () => {
      if (cyRef.current) { cyRef.current.destroy(); cyRef.current = null }
    }
  }, [sources, query])

  if (!sources?.length) return null

  return (
    <div className="mt-3 rounded-xl border border-slate-700 overflow-hidden">
      <div className="px-4 py-2 bg-slate-900 border-b border-slate-700
                      flex items-center justify-between">
        <span className="text-sm font-medium text-slate-400">📚 Source Ontology Graph</span>
        <div className="flex items-center gap-3 text-xs text-slate-600">
          <span className="flex items-center gap-1">
            <span className="inline-block w-2 h-2 rounded bg-[#bbf7d0] border border-[#16a34a]" />
            High ≥0.7
          </span>
          <span className="flex items-center gap-1">
            <span className="inline-block w-2 h-2 rounded bg-[#fef08a] border border-[#ca8a04]" />
            Med ≥0.4
          </span>
          <span className="flex items-center gap-1">
            <span className="inline-block w-2 h-2 rounded bg-[#bfdbfe] border border-[#3b82f6]" />
            Lower
          </span>
        </div>
      </div>
      <div ref={containerRef} style={{ width: "100%", height: "340px", background: "#0a0f1a" }} />
    </div>
  )
}