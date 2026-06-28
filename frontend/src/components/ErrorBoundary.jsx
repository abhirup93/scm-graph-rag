import { Component } from "react"

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { error: null }
  }

  static getDerivedStateFromError(error) {
    return { error }
  }

  componentDidCatch(error, info) {
    console.error("App error:", error, info)
  }

  render() {
    if (this.state.error) {
      return (
        <div className="flex items-center justify-center h-screen bg-[#0e1117]">
          <div className="max-w-lg p-6 bg-red-950/40 border border-red-800 rounded-xl">
            <h2 className="text-red-400 font-semibold mb-2">Something went wrong</h2>
            <pre className="text-xs text-red-300 whitespace-pre-wrap overflow-auto max-h-60">
              {this.state.error.toString()}
            </pre>
            <button
              onClick={() => this.setState({ error: null })}
              className="mt-4 px-4 py-2 bg-red-800 hover:bg-red-700
                         text-white text-sm rounded-lg transition-colors"
            >
              Try again
            </button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}
