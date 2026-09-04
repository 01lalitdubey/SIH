import { Bell, Menu, Sparkles } from "lucide-react";
import { Link } from "react-router-dom";

export default function Navbar({ onMenuClick }) {
  return (
    <header className="flex h-16 shrink-0 items-center justify-between border-b border-border bg-bg-elevated px-4 lg:px-6">
      <div className="flex items-center gap-3">
        <button
          onClick={onMenuClick}
          aria-label="Open menu"
          className="flex size-9 items-center justify-center rounded-lg text-text-secondary hover:bg-surface-hover lg:hidden"
        >
          <Menu className="size-5" aria-hidden="true" />
        </button>

        <Link to="/" className="flex items-center gap-2 lg:hidden">
          <div className="flex size-7 items-center justify-center rounded-md bg-accent-soft border border-accent/30">
            <Sparkles className="size-3.5 text-accent" aria-hidden="true" />
          </div>
          <span className="font-display text-sm font-semibold text-text-primary">SRM</span>
        </Link>
      </div>

      <div className="flex items-center gap-3">
        <button
          aria-label="Notifications"
          className="flex size-9 items-center justify-center rounded-lg text-text-secondary hover:bg-surface-hover"
        >
          <Bell className="size-4" aria-hidden="true" />
        </button>
        <div className="flex size-9 items-center justify-center rounded-full border border-border-strong bg-surface-elevated font-display text-xs font-semibold text-text-secondary">
          SIH
        </div>
      </div>
    </header>
  );
}
