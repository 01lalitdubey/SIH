import { AnimatePresence, motion, MotionConfig } from "framer-motion";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import AppShell from "./components/layout/AppShell";
import Dashboard from "./pages/Dashboard";
import Landing from "./pages/Landing";
import NotFound from "./pages/NotFound";
import Process from "./pages/Process";
import Results from "./pages/Results";

// Only crosses fade when moving between the marketing Landing page and the
// app shell — navigating within /dashboard, /process, /results keeps the
// same "app" key so the persistent Sidebar/Navbar never remount (that inner
// transition is handled by PageTransition inside AppShell instead).
function AppRoutes() {
  const location = useLocation();
  const section = location.pathname === "/" ? "landing" : "app";

  return (
    <AnimatePresence mode="wait" initial={false}>
      <motion.div
        key={section}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.25, ease: "easeOut" }}
      >
        <Routes location={location}>
          <Route path="/" element={<Landing />} />

          <Route element={<AppShell />}>
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/process" element={<Process />} />
            <Route path="/results/:jobId" element={<Results />} />
          </Route>

          <Route path="/404" element={<NotFound />} />
          <Route path="*" element={<Navigate to="/404" replace />} />
        </Routes>
      </motion.div>
    </AnimatePresence>
  );
}

export default function App() {
  return (
    <MotionConfig reducedMotion="user">
      <AppRoutes />
    </MotionConfig>
  );
}
