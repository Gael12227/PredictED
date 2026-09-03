import { NavLink } from "react-router-dom";
import { useSocket } from "../lib/ws";
import { fmt } from "../lib/format";

export function Header() {
  const { payload, connected } = useSocket();
  const sources = payload?.sources;
  const demoActive = !!sources?.demo.active;
  const mqttOk = !!sources?.mqtt.connected;
  const web = payload ? sources?.web : undefined;

  let statusClass = "status-pill pill-sim";
  let statusText = "Simulation feed";
  let dotPulse = true;
  if (mqttOk) {
    statusClass = "status-pill pill-mqtt";
    statusText = "LIVE · MQTT";
  } else if (demoActive) {
    statusClass = "status-pill pill-sim";
    statusText = "Simulation feed";
  } else if (!connected) {
    statusClass = "status-pill pill-warn";
    statusText = "Reconnecting…";
    dotPulse = false;
  }

  return (
    <header className="topbar">
      <div className="topbar-inner">
        <NavLink to="/" className="brand">
          <span className="logo">⚕</span>
          <span>
            PredictED
            <small>ED Overcrowding Intelligence</small>
          </span>
        </NavLink>

        <nav className="nav">
          <NavLink to="/" end>
            Home
          </NavLink>
          <NavLink to="/urban">Urban</NavLink>
          <NavLink to="/rural">Rural</NavLink>
        </nav>

        <div className="topbar-right">
          {web?.ok && web.aqi != null && (
            <span
              className={`status-pill ${
                web.aqi > 150 ? "pill-live" : web.aqi > 100 ? "pill-warn" : "pill-plain"
              }`}
              title="Live Delhi air quality (Open-Meteo)"
            >
              AQI {fmt(web.aqi, 0)}
            </span>
          )}
          {web?.ok && web.temperature_c != null && (
            <span className="status-pill pill-plain" title="Live Delhi weather (Open-Meteo)">
              {fmt(web.temperature_c, 0)}°C {web.weather_text}
            </span>
          )}
          <span className={statusClass}>
            <span className={`dot${dotPulse ? " pulse" : ""}`} />
            {statusText}
          </span>
        </div>
      </div>
    </header>
  );
}
