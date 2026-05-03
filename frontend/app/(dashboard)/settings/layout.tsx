"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const tabs = [
  { href: "/settings/companies", label: "Companies", desc: "Workspaces, members, branding" },
  { href: "/settings/accounts", label: "Email accounts", desc: "Gmail / M365 connectors", disabled: true },
  { href: "/settings/topics", label: "Topics", desc: "Intel filters & keywords", disabled: true },
  { href: "/settings/audit", label: "Audit log", desc: "Activity history", disabled: true },
];

export default function SettingsLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="h-full flex" style={{ background: "var(--rr-obsidian)" }}>
      {/* Settings sub-nav */}
      <nav
        className="flex flex-col py-6 px-4"
        style={{
          width: "240px",
          borderRight: "1px solid var(--rr-border)",
          background: "var(--rr-charcoal)",
          flexShrink: 0,
        }}
      >
        <h2
          className="rr-heading text-lg mb-4 px-2"
          style={{ color: "var(--rr-cream)" }}
        >
          Settings
        </h2>

        <div className="flex flex-col gap-0.5">
          {tabs.map((tab) => {
            const active = pathname === tab.href || pathname.startsWith(tab.href + "/");
            return (
              <Link
                key={tab.href}
                href={tab.disabled ? "#" : tab.href}
                aria-disabled={tab.disabled}
                className="px-3 py-2 rounded transition-colors"
                style={{
                  background: active ? "var(--rr-steel)" : "transparent",
                  borderLeft: active ? "2px solid var(--rr-brass)" : "2px solid transparent",
                  color: tab.disabled ? "var(--rr-subtle)" : active ? "var(--rr-cream)" : "var(--rr-dim)",
                  cursor: tab.disabled ? "not-allowed" : "pointer",
                  pointerEvents: tab.disabled ? "none" : "auto",
                }}
              >
                <div className="text-sm font-medium">{tab.label}</div>
                <div
                  className="text-xs mt-0.5"
                  style={{ color: tab.disabled ? "var(--rr-subtle)" : "var(--rr-subtle)" }}
                >
                  {tab.desc}
                  {tab.disabled && (
                    <span className="ml-1 rr-mono" style={{ color: "var(--rr-warn)" }}>
                      · Phase 1B+
                    </span>
                  )}
                </div>
              </Link>
            );
          })}
        </div>
      </nav>

      {/* Page content */}
      <main className="flex-1 overflow-auto">{children}</main>
    </div>
  );
}
