import { motion } from "framer-motion";
import { LayoutDashboard, ScanLine, Sparkles, X } from "lucide-react";
import { NavLink } from "react-router-dom";
import { cn } from "../../lib/cn";

const NAV_ITEMS = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/process", label: "New Analysis", icon: ScanLine },
];

function NavItem({ to, label, icon: Icon, onNavigate, scope }) {
  return (
    <NavLink
      to={to}
      onClick={onNavigate}
      className={({ isActive }) =>
        cn(
          "relative flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
          isActive
            ? "text-accent"
            : "text-text-secondary hover:bg-surface-hover hover:text-text-primary",
        )
      }
    >
      {({ isActive }) =>
        isActive ? (
          <>
            <motion.span
              layoutId={`sidebar-active-nav-${scope}`}
              transition={{ type: "spring", stiffness: 420, damping: 34 }}
              className="absolute inset-0 rounded-lg border border-accent/30 bg-accent-soft"
            />
            <Icon className="relative size-4" aria-hidden="true" />
            <span className="relative">{label}</span>
          </>
        ) : (
          <>
            <Icon className="size-4" aria-hidden="true" />
            {label}
          </>
        )
      }
    </NavLink>
  );
}

function SidebarContent({ onNavigate, scope }) {
  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-2 px-4 py-5">
        <div className="flex size-8 items-center justify-center rounded-lg bg-accent-soft border border-accent/30">
          <Sparkles className="size-4 text-accent" aria-hidden="true" />
        </div>
        <div className="leading-tight">
          <p className="font-display text-sm font-semibold text-text-primary">SRM Platform</p>
          <p className="text-[11px] text-text-muted">Super Resolution Mapping</p>
        </div>
      </div>

      <nav className="flex flex-1 flex-col gap-1 px-3 py-2">
        {NAV_ITEMS.map((item) => (
          <NavItem key={item.to} {...item} onNavigate={onNavigate} scope={scope} />
        ))}
      </nav>

      <div className="border-t border-border px-4 py-4">
        <p className="text-[11px] text-text-muted">
          Processing is currently <span className="text-warning">mocked</span> for MVP
          development.
        </p>
      </div>
    </div>
  );
}

export default function Sidebar({ mobileOpen, onClose }) {
  return (
    <>
      {/* Desktop sidebar */}
      <aside className="hidden w-64 shrink-0 border-r border-border bg-bg-elevated lg:block">
        <SidebarContent scope="desktop" />
      </aside>

      {/* Mobile drawer */}
      {mobileOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            onClick={onClose}
            aria-hidden="true"
          />
          <motion.div
            initial={{ x: -280 }}
            animate={{ x: 0 }}
            exit={{ x: -280 }}
            transition={{ type: "tween", duration: 0.2 }}
            className="relative z-50 h-full w-64 border-r border-border bg-bg-elevated"
          >
            <button
              onClick={onClose}
              aria-label="Close menu"
              className="absolute right-3 top-4 flex size-8 items-center justify-center rounded-lg text-text-secondary hover:bg-surface-hover"
            >
              <X className="size-4" aria-hidden="true" />
            </button>
            <SidebarContent onNavigate={onClose} scope="mobile" />
          </motion.div>
        </div>
      )}
    </>
  );
}
