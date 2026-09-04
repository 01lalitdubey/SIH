import { useState } from "react";
import { Outlet } from "react-router-dom";
import StarField from "../common/StarField";
import Navbar from "./Navbar";
import PageTransition from "./PageTransition";
import Sidebar from "./Sidebar";

export default function AppShell() {
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  return (
    <div className="flex h-screen bg-bg">
      <Sidebar mobileOpen={mobileNavOpen} onClose={() => setMobileNavOpen(false)} />

      <div className="flex min-w-0 flex-1 flex-col">
        <Navbar onMenuClick={() => setMobileNavOpen(true)} />
        <main className="relative flex-1 overflow-y-auto">
          <StarField count={22} className="opacity-30" />
          <div className="relative mx-auto w-full max-w-7xl px-4 py-6 lg:px-8 lg:py-8">
            <PageTransition>
              <Outlet />
            </PageTransition>
          </div>
        </main>
      </div>
    </div>
  );
}
