function RiskMeter({ score = 0, level = "LOW" }) {
  const safeScore = Math.max(0, Math.min(100, Number(score) || 0));

  const tone =
    safeScore >= 70 ? "danger" : safeScore >= 35 ? "warning" : "safe";

  return (
    <div className="risk-meter-wrap">
      <div
        className={`risk-meter tone-${tone}`}
        style={{ "--risk": `${safeScore * 3.6}deg` }}
      >
        <div className="risk-meter-inner">
          <strong>{safeScore}</strong>
          <span>/ 100</span>
        </div>
      </div>

      <div className={`risk-level-badge tone-${tone}`}>{level}</div>
    </div>
  );
}

export default RiskMeter;
