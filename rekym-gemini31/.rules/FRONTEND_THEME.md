# Frontend Theme & Styling Guidelines

Version: **2.0**
Product Type: **Consumer Fintech / Digital Wallet**
Platforms: **Web, Mobile Web, Android, iOS**
Design Goals: **Trust, clarity, speed, mass accessibility**

GCash official design system theme for the React + Tailwind CSS frontend.
Primary brand color: **`#007CFF`** (GCash Blue / gcash-b300).
Primary text color: **`#0A2757`** (navy-900 — deep slate, NOT gray).
Heading font: **Gilroy** → Inter fallback.
Body font: **Proxima Soft** → Inter fallback.

## Architecture

| Layer | File | Purpose |
|-------|------|---------|
| Design tokens | `frontend/tailwind.config.js` | `primary`, `stat`, `surface` color scales; `shadow-card`; fonts |
| Shared color maps | `frontend/src/theme/tokens.ts` | `statusStyles`, `priorityStyles`, `severityStyles`, `confidenceStyles` |
| Base defaults | `frontend/src/index.css` `@layer base` | Body bg, link colors, focus rings, input defaults |
| Component classes | `frontend/src/index.css` `@layer components` | `.btn-*`, `.card`, `.badge-*`, `.nav-link`, `.stat-card-*`, `.spinner` |

## 1. Design Principles

### 1.1 Trust by Default
Financial actions must feel safe, predictable, and reversible. Visual consistency, restrained motion, and conservative color usage reinforce user confidence.

### 1.2 Mobile-First Accessibility
Prioritize small screens, one-handed use, low bandwidth, and varying device performance.

### 1.3 Simplicity Over Density
Favor progressive disclosure, card-based grouping, and clear hierarchy over feature-heavy screens.

### 1.4 Inclusive Design
Support users with varying levels of financial literacy, language proficiency, and digital experience.

## 2. Color System

### 2.1 Core Palette
- **GCash Blue (`primary-*`)**: `#007CFF` (500) — primary actions, navigation, highlights, trust anchor
- **Navy (`navy-*`)**: `#0A2757` (900) — primary text, headings, borders. Replaces generic gray for all text.
- **White**: primary background
- **Blue-tinted surfaces (`surface`)**: `#F6F9FD` (navy-50) — page bg; `#EEF2F9` (navy-100) — section bg
- **Teal (`teal-*`)**: `#10BCB4` — info alerts, stat highlights
- **Mango (`warning-*`)**: `#F9A60B` — GCash amber/warning

### 2.2 Semantic Colors
- **Success**: `#27C990` (GCash green) — transaction completed, positive status
- **Warning**: `#F9A60B` (GCash mango) — pending, attention needed
- **Error**: `#D61B2C` (GCash red) — failed transactions, validation errors
- **Info**: `#10BCB4` (GCash teal) — tips, system messages

### 2.3 Usage Rules
- Primary blue should dominate CTAs and navigation.
- Avoid multiple accent colors on a single screen.
- Error and warning colors must never be used decoratively.

## 3. Typography System

### 3.1 Font Family
- **Display / Headings**: Gilroy (semibold/bold). Falls back to Inter, system-ui.
- **Body / UI**: Proxima Soft (regular/medium). Falls back to Inter, Segoe UI, Roboto, system-ui.
- **Monospace**: Fira Code.
- Premium fonts (Gilroy, Proxima Soft) require Adobe Fonts license or self-hosting. Inter is loaded from Google Fonts as the default fallback.

### 3.2 Type Scale
GCash type scale tokens in Tailwind: `gcash-caption` (12px) → `gcash-h1` (40px).
Headings use negative letter-spacing (`tracking-gcash-h1` through `tracking-gcash-h5`).

### 3.3 Typography Rules
- Numbers must be visually distinct.
- Keep line length optimized for mobile reading.
- Avoid long paragraphs; use short, scannable text blocks.

## 4. Layout & Grid

### 4.1 Grid System
- Single-column layout on mobile.
- Responsive multi-column layout on desktop.
- Consistent horizontal padding.

### 4.2 Card-Based Architecture
Cards are the primary organizational unit (wallet summary, recent transactions, services/features). Each card should include:
- Clear header
- Primary action (if applicable)
- Optional secondary actions

## 5. Navigation

### 5.1 Primary Navigation
- Bottom navigation bar on mobile.
- Icon + label pattern.
- Maximum 4-5 primary destinations.

### 5.2 Secondary Navigation
- Contextual tabs within sections.
- Back navigation always visible.

### 5.3 Navigation Rules
- Primary payment actions must be reachable in ≤ 2 taps.
- Navigation labels should use common financial language.

## 6. Buttons & CTAs

### 6.1 Button Types
- **Primary Button**: solid GCash Blue, white text, rounded corners
- **Secondary Button**: outline or lighter fill, lower visual priority
- **Tertiary/Text Button**: no container, for low-risk actions

### 6.2 Button States
- Default
- Pressed
- Disabled
- Loading (with spinner)

## 7. Iconography

### 7.1 Icon Style
- Flat, line-based icons
- Rounded corners
- Consistent stroke weight

### 7.2 Usage Guidelines
- Always pair icons with text labels.
- Icons should reinforce meaning, not replace it.
- Avoid decorative icons in transactional flows.

## 8. Imagery & Illustrations

### 8.1 Photography
- Keep usage minimal.
- Keep imagery functional, not aspirational.
- Avoid luxury/lifestyle-heavy imagery.

### 8.2 Illustrations
- Use for onboarding, promotions, and education.
- Keep style friendly, simple, and culturally neutral.

## 9. Motion & Feedback

### 9.1 Animation Principles
- Fast and subtle.
- Purpose-driven (feedback, progress, confirmation).

### 9.2 Feedback Patterns
- Show immediate visual confirmation for actions.
- Provide clear success and failure states.
- Avoid long blocking animations.

## 10. Accessibility

### 10.1 Readability
- Maintain high color contrast.
- Enforce minimum font sizes.

### 10.2 Interaction
- Ensure large tap targets.
- Preserve clear focus states.

### 10.3 Language
- Use plain language.
- Avoid technical or banking jargon when possible.

## 11. Tone & Microcopy

### 11.1 Voice
- Clear
- Reassuring
- Neutral and respectful

### 11.2 Copy Guidelines
- Use short sentences.
- Prefer action-oriented CTAs.
- Require explicit confirmation for money-related actions.

## 12. Design System Summary

The GCash design system prioritizes clarity, trust, and speed. It balances fintech reliability with consumer-friendly simplicity, ensuring digital financial services are accessible to a broad and diverse user base.

## Implementation in This Codebase

### How New Pages/Components Inherit Theme

Unstyled elements auto-inherit GCash styling from `@layer base`:
- **Body**: `bg-surface` (`#F6F9FD`), `text-navy-900` (`#0A2757`)
- **Headings**: `font-display` (Gilroy), `font-semibold`, `tracking-gcash-*` negative letter-spacing
- **Links**: `text-primary-600` with `hover:text-primary-700`
- **Focus rings**: `ring-2 ring-primary-500 ring-offset-2` on `:focus-visible`
- **Inputs/selects/textareas**: `rounded-lg border-navy-300` with primary focus ring

New components should use component classes:
```jsx
<div className="page-container">
  <h1 className="page-title">New Page</h1>
  <div className="card">Content auto-themed</div>
  <button className="btn-primary">Save</button>
</div>
```

### Available Component Classes

#### Buttons
| Class | Usage |
|-------|-------|
| `.btn-primary` | Primary actions — GCash blue bg, white text |
| `.btn-secondary` | Secondary/cancel — white bg, gray border |
| `.btn-danger` | Destructive actions — red bg |
| `.btn-warning` | Caution actions — amber bg |

#### Cards & Layout
| Class | Usage |
|-------|-------|
| `.card` | Standard card — white bg, rounded-xl, shadow-card |
| `.card-hover` | Interactive card — adds hover lift + shadow |
| `.page-container` | Page wrapper — max-w-7xl, responsive padding |
| `.page-title` | H1 heading — 2xl bold, `font-display` (Gilroy), `tracking-gcash-h2`, navy-900 |
| `.page-subtitle` | Subheading — sm navy-600 |

#### Badges
| Class | Usage |
|-------|-------|
| `.badge` | Base badge — rounded-full, xs font |
| `.badge-primary` | Primary — GCash blue tint |
| `.badge-success` | Success — green |
| `.badge-warning` | Warning — yellow |
| `.badge-danger` | Danger — red |
| `.badge-neutral` | Neutral — navy tint |

#### Navigation, Feedback, Tables, Modals
| Class | Usage |
|-------|-------|
| `.nav-link` | Nav item — navy, hover primary |
| `.nav-link-active` | Active nav — primary bg tint |
| `.spinner` | Loading spinner — primary-600 border |
| `.spinner-sm` | Small spinner (in buttons) |
| `.stat-card-blue/teal/violet/emerald` | Dashboard stat cards |
| `.table-header` | Table column header |
| `.table-row-hover` | Hoverable table row |
| `.modal-backdrop` | Modal overlay |
| `.modal-panel` | Modal content panel |

### Shared Color Maps (`theme/colors.ts`)

Import these instead of defining inline maps in components:
```tsx
import { statusStyles, priorityStyles } from '../theme/tokens';

<span className={`badge ${statusStyles[case.status]}`}>
  {case.status}
</span>
```

Available exports: `statusStyles`, `priorityStyles`, `severityStyles`, `confidenceStyles`.

### Enforced Rules

1. **Never hardcode `blue-*`, `indigo-*`, or `gray-*`** for interactive elements — use `primary-*` tokens for blue and `navy-*` for neutral text/borders.
2. **Use component classes** (`.btn-primary`, `.card`, etc.) for standard UI patterns — do not reinvent button/card styles inline.
3. **Import from `theme/tokens.ts`** for status/priority/severity badges — do not duplicate maps in components.
4. **Semantic colors stay semantic** — red for danger, mango/amber for warning, green for success, teal for info.
5. **Dashboard stat cards** use blue-shifted complementary hues (`stat.blue`, `stat.teal`, `stat.violet`, `stat.emerald`).
6. **CSS custom properties** in `:root` (`--color-primary`, `--color-surface`, `--color-text`, etc.) are available for edge cases outside Tailwind.
7. **Navy replaces gray for text** — use `text-navy-*` / `border-navy-*` instead of `text-gray-*` / `border-gray-*`.

## Changing the Theme

To rebrand, update these files only:
1. `frontend/tailwind.config.js` — change the `primary`, `navy`, and semantic color scales
2. `frontend/src/index.css` — update `:root` and `:root.dark` CSS custom properties and base layer
3. `frontend/src/theme/tokens.ts` — update shared TS color maps (`colors`, badge styles)
4. `frontend/index.html` — update font import links if changing typefaces
5. No component files need to change (they should reference tokens and shared classes)

## Dark Mode

The app supports light and dark mode. User preference is persisted in `localStorage` (key: `rekym-theme`) and applied via a `dark` class on `<html>`. Tailwind is configured with `darkMode: "class"`.

### Architecture

| Layer | Mechanism |
|-------|----------|
| Theme toggle | `useTheme()` hook (`frontend/src/hooks/use-theme.ts`) — reads/writes localStorage, toggles `dark` class |
| FOUC prevention | Inline `<script>` in `frontend/index.html` — applies `dark` class before React hydrates |
| CSS variables | `:root.dark` block in `frontend/src/index.css` — overrides `--color-surface`, `--color-text`, etc. |
| Tailwind | `darkMode: "class"` in `frontend/tailwind.config.js` |
| Component classes | `dark:` variants on all `.btn-*`, `.card`, `.badge-*`, `.table-*`, `.modal-*`, etc. in `@layer components` |
| Token maps | `dark:` classes embedded in every badge style string in `frontend/src/theme/tokens.ts` |

### Rules for Every Frontend Change

1. **Every visible text color must have a `dark:` variant.** If you write `text-navy-700`, also add `dark:text-[var(--color-text-secondary)]` (or an appropriate light-on-dark color). Text that is invisible on a dark background is a blocker.
2. **Every `bg-white` must have a `dark:` variant.** Use `dark:bg-[var(--color-surface-card)]` for cards/panels, `dark:bg-[var(--color-surface-alt)]` for secondary surfaces.
3. **Every `border-navy-*` must have a `dark:` variant.** Use `dark:border-[var(--color-border)]`.
4. **Badge/status token strings must include `dark:` classes.** When adding entries to `caseStateColors`, `statusStyles`, `priorityStyles`, etc., always add `dark:bg-*` and `dark:text-*` alongside the light-mode classes.
5. **Prefer CSS custom properties** (`var(--color-text)`, `var(--color-surface)`) for dark variants — they auto-switch between `:root` and `:root.dark`.
6. **Sidebar uses a separate dark palette.** The sidebar gradient switches from `from-primary-600 to-primary-700` (light) to `dark:from-[#060F2E] dark:to-[#0B1929]` (dark). Nav link text uses `dark:text-white/80`.
7. **Test both modes visually** before marking frontend work complete. Toggle the theme and verify all text is readable, all borders are visible, and no element disappears.

### Dark Mode CSS Custom Properties

Defined in `:root.dark` in `frontend/src/index.css`:

| Property | Light | Dark | Usage |
|----------|-------|------|-------|
| `--color-surface` | `#F6F9FD` | `#0B1929` | Page background |
| `--color-surface-alt` | `#EEF2F9` | `#0F2137` | Secondary surface |
| `--color-surface-card` | `#FFFFFF` | `#132D4A` | Card/panel background |
| `--color-border` | `#E0E8F3` | `#1E3A5F` | Borders |
| `--color-text` | `#0A2757` | `#E0E8F3` | Primary text |
| `--color-text-secondary` | `#445C85` | `#ADBDDC` | Secondary text (labels, metadata) |
| `--color-text-tertiary` | `#6780A9` | `#7E96BE` | Tertiary text (timestamps, hints) |
| `--color-text-muted` | `#7E96BE` | `#6780A9` | Muted text (helper text) |
