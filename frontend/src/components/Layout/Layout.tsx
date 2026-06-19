import { NavLink, Outlet } from "react-router-dom"

const navLinks = [
  { to: "/", label: "Home" },
  { to: "/generate", label: "Generate" },
  { to: "/recommendations", label: "Recommendations" },
]

export default function Layout() {
  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      <nav className="border-b border-gray-800 px-6 py-4 flex items-center gap-8">
        <span className="font-semibold tracking-tight">Playlist Recommender</span>
        <div className="flex gap-6">
          {navLinks.map(({ to, label }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              className={({ isActive }) =>
                isActive ? "text-white" : "text-gray-400 hover:text-gray-200 transition-colors"
              }
            >
              {label}
            </NavLink>
          ))}
        </div>
      </nav>
      <main className="px-6 py-8">
        <Outlet />
      </main>
    </div>
  )
}
