# Design — FraudLens: Design System & UX Principles

| Field | Value |
| --- | --- |
| Version | v0.1 |
| Last Updated | 2026-08-06 |
| Owner | Design Lead |
| Status | In Review |

---

## 1. Design Principles

1. **Decision-ready** — every screen serves a decision (flag/close/promote).
2. **Explainability first** — SHAP and narrations are first-class UI.
3. **Calm urgency** — red used sparingly; only true risk.
4. **Consistent density** — tables + charts, minimal prose.
5. **Trustworthy numbers** — every figure labeled with source/timestamp.

## 2. Brand & Visual Identity

- Voice: analytical, professional.
- Imagery: charts and transaction tables; no decorative imagery.

## 3. Color System

| Token | Hex | Usage | Contrast (AA) |
| --- | --- | --- | --- |
| bg | `#0F172A` | dark dashboard bg | — |
| surface | `#1E293B` | cards | — |
| text | `#F1F5F9` | primary text | 12:1 |
| muted | `#94A3B8` | secondary text | 7:1 |
| risk-high | `#EF4444` | high risk | 5.5:1 |
| risk-medium | `#F59E0B` | medium risk | 4.8:1 |
| risk-low | `#22C55E` | low risk | 5:1 |
| accent | `#3B82F6` | CTAs, links | 5.8:1 |

## 4. Typography Scale

| Token | Font | Size | Weight | Line-height | Usage |
| --- | --- | --- | --- | --- | --- |
| display | system sans | 28px | 700 | 1.2 | KPI numbers |
| heading | system sans | 20px | 600 | 1.3 | page headers |
| body | system sans | 14px | 400 | 1.5 | content |
| table | mono | 13px | 400 | 1.4 | transaction tables |
| label | system sans | 12px | 600 | 1.4 | field labels |

## 5. Spacing & Grid

- Base 4px; Streamlit default layout with custom theme.
- Breakpoints: Streamlit handles responsive.

## 6. Component Library

**Risk badge:**

```
┌──────────┐
│ ● HIGH   │  ← color-coded pill
└──────────┘
variants: HIGH (red), MEDIUM (amber), LOW (green)
```

**SHAP force plot** — rendered via SHAP library into the Case Investigator.

Other components: KPI card, transaction table, metric chart (Plotly), governance table with approve/reject buttons, chat panel, config panel.

## 7. Iconography

Minimal — Plotly icons + Unicode; no image assets.

## 8. Accessibility

- WCAG 2.1 AA targets; risk never conveyed by color alone (badge text included).
- Keyboard navigation in tables and chat.

## 9. Responsive

- Dashboard fluid; tables scroll horizontally on small screens.

## 10. Motion

- Minimal: chart transitions (300ms), stream update pulses.
- `prefers-reduced-motion` honored.

## 11. Dark Mode

Dark-first theme (dashboard is dark by default).

## 12. Related Documents

| Document | Relationship |
| --- | --- |
| [AppFlow.md](AppFlow.md) | Screens consuming components |
| [PRD.md](../product/PRD.md) | UX goals |
| [TechSpec.md](../technical/TechSpec.md) | Dashboard stack |
| [Schema.md](../technical/Schema.md) | Data displayed |
| [ImplementationPlan.md](../project/ImplementationPlan.md) | Tasks |
| [Tracker.md](../project/Tracker.md) | Status |
| [Rules.md](../project/Rules.md) | Standards |
| [API.md](../technical/API.md) | Data contracts |
| [SecurityAndCompliance.md](../technical/SecurityAndCompliance.md) | Access |
| [Testing.md](../technical/Testing.md) | UI tests |
| [Deployment.md](../technical/Deployment.md) | Deploy |
| [Glossary.md](../reference/Glossary.md) | Vocabulary |
| [RiskRegister.md](../project/RiskRegister.md) | Risks |
