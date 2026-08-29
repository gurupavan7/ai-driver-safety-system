function StatusCard({
  label,
  value,
  subtitle,
  tone = "neutral",
  compact = false,
}) {
  return (
    <div className={`card status-card ${compact ? "compact" : ""}`}>
      <div className="card-label">{label}</div>
      <div className={`card-value tone-${tone}`}>{value}</div>
      {subtitle && <div className="card-subtitle">{subtitle}</div>}
    </div>
  );
}

export default StatusCard;
