"use client";

// Graceful error boundary for the dashboard — a runtime error in any card
// or chart shouldn't blank the whole page mid-demo.

import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // eslint-disable-next-line no-console
    console.error("MemoryOS error boundary caught:", error, info);
  }

  reset = () => this.setState({ error: null });

  render() {
    if (this.state.error) {
      return (
        this.props.fallback ?? (
          <div className="card border-danger/40 bg-danger/5 p-5">
            <h3 className="text-sm font-semibold text-danger">
              Something went wrong in this panel
            </h3>
            <p className="mt-1 text-xs text-muted">{this.state.error.message}</p>
            <button
              onClick={this.reset}
              className="mt-3 rounded-md border border-line px-3 py-1 text-xs transition-colors hover:border-accent/40 hover:text-accent"
            >
              Retry
            </button>
          </div>
        )
      );
    }
    return this.props.children;
  }
}
