import { useState } from 'react'
import { Link } from 'react-router-dom'
import { LanguageToggle } from '../../../components/shared/LanguageToggle'
import { ThemeToggle } from '../../../components/shared/ThemeToggle'
import { useLanguage } from '../../../lib/i18n/useLanguage'
import { ablationRows, designPillars, keyMetrics, productFlows } from '../websiteData'

const navSections = ['Research', 'Dashboard', 'Results', 'About', 'Contact'] as const

export function WebsitePage() {
  const { t } = useLanguage()
  const [menuOpen, setMenuOpen] = useState(false)

  return (
    <div className="website-page">
      <header className="site-header">
        <div className="nav-shell">
          <Link className="brand" to="/">
            <span className="brand-mark">⌁</span>
            <span className="brand-name">
              <strong>AgMultida</strong>
              <span>AI irrigation decision surface</span>
            </span>
          </Link>
          <nav className="nav-links" aria-label="Main navigation">
            {navSections.map((section) => (
              <a key={section} href={`#${section.toLowerCase()}`}>{t(section)}</a>
            ))}
          </nav>
          <div className="nav-actions">
            <LanguageToggle />
            <ThemeToggle />
            <button className="icon-button hamburger" type="button" onClick={() => setMenuOpen((value) => !value)} aria-label="Toggle menu">≡</button>
            <Link className="btn primary desktop-only" to="/dashboard">{t('Access Dashboard')}</Link>
          </div>
        </div>
        {menuOpen && (
          <div className="mobile-menu">
            {navSections.map((section) => (
              <a key={section} href={`#${section.toLowerCase()}`} onClick={() => setMenuOpen(false)}>{t(section)}</a>
            ))}
            <Link className="btn primary" to="/dashboard" onClick={() => setMenuOpen(false)}>{t('Access Dashboard')}</Link>
          </div>
        )}
      </header>

      <section className="hero" id="home">
        <div className="hero-canvas" aria-hidden="true">
          <div className="field-grid" />
        </div>
        <div className="hero-content">
          <div>
            <span className="eyebrow"><span className="dot" />Multimodal crop monitoring / irrigation decision support</span>
            <h1>Open dashboard. Select zone. Run model. See result instantly.</h1>
            <p className="hero-subtitle">
              AgMultida turns zone selection into a visible AI workflow: water-stress prediction, irrigation recommendation, and zone status with confidence and reasoning shown directly on screen.
            </p>
            <div className="hero-actions">
              <Link className="btn primary" to="/dashboard">{t('Open Full Dashboard')}</Link>
              <a className="btn ghost" href="#research">View Research</a>
            </div>
          </div>
          <aside className="hero-status">
            <h3>{t('System Snapshot')}</h3>
            {keyMetrics.map((metric) => (
              <div className="status-row" key={metric.label}>
                <span>{metric.label}</span>
                <strong>{metric.value}</strong>
              </div>
            ))}
          </aside>
        </div>
      </section>

      <section className="section" aria-labelledby="capabilities-title">
        <div className="section-head">
          <div>
            <span className="section-kicker">Product surface</span>
            <h2 id="capabilities-title">Three product functions, each with direct model output.</h2>
          </div>
          <p className="section-lead">Frontend must answer what goes in, what comes out, and what decision follows. No vague AI box.</p>
        </div>
        <div className="product-flow-grid">
          {productFlows.map((flow) => (
            <article className="website-card flow-card" key={flow.title}>
              <h3>{flow.title}</h3>
              <div className="flow-meta"><span>{t('Input')}</span><strong>{flow.input}</strong></div>
              <div className="flow-meta"><span>{t('Output')}</span><strong>{flow.output}</strong></div>
              <div className="flow-meta"><span>{t('Decision')}</span><strong>{flow.decision}</strong></div>
            </article>
          ))}
        </div>
      </section>

      <section className="section" aria-labelledby="philosophy-title">
        <div className="section-head">
          <div>
            <span className="section-kicker">Design rules</span>
            <h2 id="philosophy-title">Model behavior stays visible from first screen to final action.</h2>
          </div>
          <p className="section-lead">This product is not a brochure. It is a working decision surface for zone-level irrigation operations.</p>
        </div>
        <div className="pillar-grid">
          {designPillars.map((pillar) => (
            <article className="pillar-card" key={pillar.title}>
              <span className="badge">{pillar.title}</span>
              <p>{pillar.copy}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="section dashboard-preview-section" id="dashboard" aria-labelledby="dashboard-title">
        <div className="section-head">
          <div>
            <span className="section-kicker">Result-first preview</span>
            <h2 id="dashboard-title">Every click on dashboard must reveal a concrete model result.</h2>
          </div>
          <p className="section-lead">Prediction shows stress score and uncertainty. Recommendation shows action and volume. Zone status shows latest state.</p>
        </div>
        <div className="preview-grid preview-grid-2">
          <article className="preview-panel result-panel-preview">
            <h3>Prediction / Zone A03</h3>
            <div className="stress-value">78%</div>
            <div className="result-preview-meta">
              <span>confidence: low</span>
              <span>uncertainty: 0.34</span>
              <span>latency: 420 ms</span>
            </div>
          </article>
          <article className="preview-panel result-panel-preview">
            <h3>Recommendation / Zone A03</h3>
            <div className="stress-value">28 mm</div>
            <div className="result-preview-meta">
              <span>action: heavy</span>
              <span>reason: critical_stress_low_moisture</span>
              <span>require_ack: true</span>
            </div>
            <Link className="btn primary" to="/dashboard">{t('Open Full Dashboard')}</Link>
          </article>
        </div>
      </section>

      <section className="section" id="research" aria-labelledby="research-title">
        <div className="section-head">
          <div>
            <span className="section-kicker">Research</span>
            <h2 id="research-title">Model path: multimodal input, prediction output, irrigation decision.</h2>
          </div>
          <p className="section-lead">Research content stays visible, but now tied directly to product output fields the operator can read.</p>
        </div>
        <div className="research-layout">
          <div className="stack-grid">
            <article className="research-panel">
              <h3>Operational explanation</h3>
              <p>Input = image + sensor + weather. Output = stress probability + uncertainty. Decision = irrigation action + volume + reason.</p>
              <div className="badge-row">
                <span className="badge">stress_prob</span>
                <span className="badge">uncertainty</span>
                <span className="badge">reason</span>
              </div>
            </article>
            <article className="research-panel">
              <h3>Dataset schema</h3>
              <pre className="code-block">{`{
  "zone_id": "A03",
  "timestamp": "2026-05-08T08:42:00Z",
  "stress_prob": 0.78,
  "uncertainty": 0.34,
  "action": "heavy",
  "volume_mm": 28
}`}</pre>
            </article>
          </div>
          <div className="diagram" aria-label="Architecture diagram">
            <div className="diagram-node image">Image input</div>
            <div className="diagram-node sensor">Sensor input</div>
            <div className="diagram-node weather">Weather input</div>
            <div className="diagram-node fusion">Model prediction</div>
            <div className="diagram-node output">Stress output</div>
            <div className="diagram-node rule">Irrigation decision</div>
          </div>
        </div>
      </section>

      <section className="section" id="results" aria-labelledby="results-title">
        <div className="section-head">
          <div>
            <span className="section-kicker">Results</span>
            <h2 id="results-title">Research credibility remains, but product outputs stay primary.</h2>
          </div>
          <p className="section-lead">Ablation, calibration, and robustness still matter because they explain trust in the same outputs users see on dashboard.</p>
        </div>
        <div className="chart-grid">
          <article className="chart-box">
            <h4>Ablation Table</h4>
            <table>
              <thead>
                <tr><th>Model</th><th>F1</th><th>ECE</th><th>Missing Modality</th></tr>
              </thead>
              <tbody>
                {ablationRows.map((row) => (
                  <tr key={row[0]}>{row.map((cell) => <td key={cell}>{cell}</td>)}</tr>
                ))}
              </tbody>
            </table>
          </article>
          <article className="chart-box"><h4>Confusion Matrix</h4><div className="matrix"><span className="strong">92</span><span>6</span><span>2</span><span>8</span><span className="strong">84</span><span>8</span><span>3</span><span>9</span><span className="strong">88</span></div></article>
          <article className="chart-box"><h4>Calibration Plot</h4><svg className="line-chart" viewBox="0 0 520 150"><path d="M28 126 L490 20" className="chart-axis" /><path d="M28 122 C98 116 136 94 206 88 S314 54 372 48 S446 32 490 24" className="chart-stress" /></svg></article>
        </div>
      </section>

      <section className="section" id="about">
        <div className="section-head">
          <div><span className="section-kicker">About</span><h2>Built to connect research logic with field decisions.</h2></div>
          <p className="section-lead">The frontend now centers operator understanding: what the model saw, what it predicted, and why it recommends an action.</p>
        </div>
        <div className="timeline">
          <div><strong>Phase 1 / Water Stress</strong><p>Prediction, irrigation recommendation, and zone status unified on one dashboard.</p></div>
          <div><strong>Phase 2 / Nutrient and Pest</strong><p>Expand diagnosis families while keeping output cards explicit and explainable.</p></div>
          <div><strong>Phase 3 / Scale</strong><p>Multi-farm deployment with map-first operations and stable backend contracts.</p></div>
        </div>
      </section>

      <section className="section" id="contact">
        <div className="section-head">
          <div><span className="section-kicker">Contact</span><h2>Ready for pilot review, product feedback, and field testing.</h2></div>
          <p className="section-lead">Use dashboard path to evaluate UX and model visibility before broader backend integration.</p>
        </div>
        <div className="contact-card"><h3>Collaboration Request</h3><p className="section-copy">Landing page now explains exactly what user gets from the system before they enter dashboard.</p></div>
      </section>
    </div>
  )
}
