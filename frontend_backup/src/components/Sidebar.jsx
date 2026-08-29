import { NavLink } from "react-router-dom";

const links = [
  { name: "Dashboard", path: "/" },
  { name: "Analytics", path: "/analytics" },
  { name: "History", path: "/history" },
  { name: "Settings", path: "/settings" },
];

function Sidebar() {
  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-icon">AI</div>
        <div>
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
            {link.name}
          </NavLink>
        ))}
      </nav>

      <div className="sidebar-footer">
        <span className="status-dot"></span>
        AI Monitoring System
      </div>
    </aside>
  );
}

export default Sidebar;