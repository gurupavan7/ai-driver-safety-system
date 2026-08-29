import { NavLink } from "react-router-dom";

const links = [
  { name: "Dashboard", path: "/", icon: "◫" },
  { name: "Analytics", path: "/analytics", icon: "⌁" },
  { name: "History", path: "/history", icon: "↺" },
  { name: "Video Analyzer", path: "/video-analyzer", icon: "▶" },
  { name: "Settings", path: "/settings", icon: "⚙" },
];

function Sidebar() {
  return (
    <aside className="sidebar">
      <div>
        <div className="brand">
          <div className="brand-icon">DG</div>

          <div className="brand-copy">
            <h2>DriverGuard</h2>
            <span>AI Safety System</span>
          </div>
        </div>

        <nav className="nav-links">
          {links.map((link) => (
            <NavLink
              key={link.path}
              to={link.path}
              end={link.path === "/"}
              className={({ isActive }) =>
                isActive ? "nav-link active" : "nav-link"
              }
            >
              <span className="nav-icon">{link.icon}</span>
              <span>{link.name}</span>
            </NavLink>
          ))}
        </nav>
      </div>

      <div className="sidebar-footer">
        <span className="status-dot" />
        <div>
          <strong>System Online</strong>
          <span>AI monitoring</span>
        </div>
      </div>
    </aside>
  );
}

export default Sidebar;
