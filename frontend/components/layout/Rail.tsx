"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const rooms = [
  { href: "/morning", label: "Morning Room", icon: "☀", desc: "Daily dispatch" },
  { href: "/wire", label: "The Wire", icon: "⚡", desc: "Intelligence feed" },
  { href: "/comms", label: "Comms Hub", icon: "✉", desc: "Canvas board" },
  { href: "/team", label: "Team View", icon: "◈", desc: "Delegations" },
  { href: "/intelligence", label: "Intelligence", icon: "◉", desc: "Opportunity radar" },
  { href: "/map", label: "Map Room", icon: "⊕", desc: "Geopolitics" },
  { href: "/blacklist", label: "Blacklist", icon: "◎", desc: "Entity dossiers" },
  { href: "/library", label: "Library", icon: "≡", desc: "Sector intel" },
  { href: "/vault", label: "Vault", icon: "◇", desc: "Ventures" },
  { href: "/concierge", label: "Concierge", icon: "⊞", desc: "Deal pipeline" },
  { href: "/rolodex", label: "Rolodex", icon: "⊛", desc: "Network" },
  { href: "/ledger", label: "Ledger", icon: "$", desc: "Capital" },
  { href: "/war-room", label: "War Room", icon: "⊡", desc: "Tasks" },
];

export default function Rail() {
  const pathname = usePathname();

  return (
    <nav
      className="flex flex-col h-full overflow-y-auto"
      style={{
        width: "200px",
        background: "var(--rr-charcoal)",
        borderRight: "1px solid var(--rr-border)",
        flexShrink: 0,
      }}
    >
      {/* Logo */}
      <div
        className="flex items-center gap-2 px-4 py-3 border-b"
        style={{ borderColor: "var(--rr-border)" }}
      >
        <span style={{ color: "var(--rr-brass)", fontSize: "18px" }}>RR</span>
        <span className="rr-heading text-sm" style={{ color: "var(--rr-cream)" }}>
          Command
        </span>
      </div>

      {/* Rooms */}
      <div className="flex flex-col py-2 gap-0.5">
        {rooms.map((room) => {
          const active = pathname === room.href || pathname.startsWith(room.href + "/");
          return (
            <Link
              key={room.href}
              href={room.href}
              className="flex items-center gap-3 px-4 py-2 mx-2 rounded transition-all text-sm"
              style={{
                color: active ? "var(--rr-cream)" : "var(--rr-dim)",
                background: active ? "var(--rr-steel)" : "transparent",
                borderLeft: active ? "2px solid var(--rr-brass)" : "2px solid transparent",
              }}
            >
              <span style={{ color: active ? "var(--rr-brass)" : "var(--rr-subtle)", width: "16px", textAlign: "center" }}>
                {room.icon}
              </span>
              <span>{room.label}</span>
            </Link>
          );
        })}
      </div>

      {/* Settings */}
      <div className="mt-auto border-t p-3" style={{ borderColor: "var(--rr-border)" }}>
        <Link
          href="/settings/companies"
          className="flex items-center gap-2 text-xs px-2 py-1 rounded"
          style={{
            color: pathname.startsWith("/settings") ? "var(--rr-cream)" : "var(--rr-subtle)",
          }}
        >
          <span>⚙</span>
          <span>Settings</span>
        </Link>
      </div>
    </nav>
  );
}
