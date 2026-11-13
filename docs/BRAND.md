# Hivemind brand

The Hivemind brand kit lives in [`/brand`](../brand). It is the source of truth: open
[`brand/board.html`](../brand/board.html) (or [`board.png`](../brand/board.png)) for the
board. This page explains how the product applies the kit. Everything under "Product tokens"
is derived from the kit for UI use. It extends the kit and does not replace it.

> Six agents draw the cell. The amber hex is the mind that appears between them.

## Kit assets

| File | Use |
| --- | --- |
| `brand/mark.svg` | The mark on light backgrounds (Ink cell, Signal hex) |
| `brand/mark-on-dark.svg` | Reversed: Paper cell, On-ink hex. Used in the product nav |
| `brand/mark-mono.svg` | One colour, Ink only |
| `brand/logo.svg`, `brand/logo-dark.svg` | Horizontal lockup (mark + wordmark) |
| `brand/logo-stacked.svg`, `brand/logo-stacked-dark.svg` | Stacked lockup |
| `brand/icon.svg`, `brand/icon.png` | App icon: the mark on an Ink rounded square |
| `brand/*.png` | Raster versions of the above |

In the app:

- `frontend/public/favicon.svg` is a copy of `brand/icon.svg`.
- `frontend/public/icon.png` is a copy of `brand/icon.png`.
- `frontend/src/assets/brand/` holds copies of `mark.svg` and `mark-on-dark.svg`.
- `frontend/src/components/HivemindMark.vue` draws the same geometry inline. Home uses it
  for the animated mark: the six agent dashes travel round the cell and the amber hex
  appears between them. Reduced-motion users see it still.

Don't redraw, recolour or re-letter the mark. Use the files.

## Colour

From the kit:

| Name | Hex | Role |
| --- | --- | --- |
| Ink | `#16140F` | Text, the nav bar, dark panels |
| Paper | `#F3F0E8` | The page |
| Signal | `#D4890A` | Amber on light. The single accent |
| On ink | `#F0A818` | Amber on dark |
| Muted | `#8A8478` | Board labels; secondary text on Ink |
| Line | `#E4DDD2` | Rules |

Rules:

- **Pages sit on Paper with Ink text.** Cards, inputs, menus and dialogs are white
  (`#FFFFFF`) on Paper.
- **Signal is the single accent.** Use it for primary actions, active, current and live
  states, and focus. Text on a Signal fill is Ink (6.5:1). Never set Signal as text on
  Paper or white (2.5:1).
- **On ink replaces Signal on dark surfaces**: the nav bar and the log consoles.
- **Never use the brand amber as a data colour.** It collides with the yellow and orange
  series in the chart palette (`frontend/src/components/analytics/palette.js`). That
  palette was validated for colour-vision deficiency against white, so chart cards stay
  white on the Paper page.
- Status colours (success green, danger red) are for status only, never decoration.

## Type

- **Space Grotesk**: the wordmark (Medium) and all product text. Headings use weight 500
  with tight tracking (`-0.02em` to `-0.035em`).
- **JetBrains Mono**: the nav, labels, IDs, timestamps, numbers in logs and code. Labels
  are 11px uppercase with `0.14em` tracking, as on the board.
- Noto Sans SC is the fallback for Chinese.

Scale (tokens `--hm-text-*`): 11, 12, 13, 14 (body), 16, 18, 22, 28, 40, 60px.

## The product nav

From the board's "In the product" panel, it appears on every view and is implemented in
`frontend/src/components/AppHeader.vue`.

- A full-width Ink bar, 60px tall, with 28px side padding.
- Left: `mark-on-dark` at 22px, then **HIVEMIND** in JetBrains Mono 700, 15px, `0.14em`
  tracking, in Paper.
- Right: **GITHUB** in JetBrains Mono, 12px, `0.08em` tracking, in `#B7B1A6`.
- Workspace views add, in the same mono idiom:
  - a five-cell hex step track (done cells Paper, the current one On ink);
  - the layout switch;
  - a status pill;
  - the language menu.

## Product tokens

All tokens are CSS custom properties in `frontend/src/styles/hivemind.css`, which is
imported once in `src/main.js`.

| Group | Tokens |
| --- | --- |
| Kit | `--hm-ink`, `--hm-paper`, `--hm-signal`, `--hm-on-ink`, `--hm-muted`, `--hm-line`, `--hm-nav-text` |
| Ink scale | `--hm-ink-2` `#37332B`, `--hm-ink-3` `#555048`, `--hm-ink-4` `#736D63` (smallest AA text on Paper), `--hm-ink-5` `#A7A196` (placeholder and disabled only) |
| Surfaces | `--hm-surface` `#FFFFFF`, `--hm-surface-2` `#F8F6F1`, `--hm-surface-3` `#EDE9E0`, `--hm-line-strong` `#D2CABD` |
| Signal states | `--hm-signal-hover` `#B87505`, `--hm-signal-soft` `#F7E9CB`, `--hm-signal-ink` `#7A4D00` (text on Signal soft) |
| Status | `--hm-success*`, `--hm-danger*` (text, dot, soft) |
| Consoles | `--hm-console-bg` (Ink), `--hm-console-raised`, `--hm-console-line`, `--hm-console-text`, `--hm-console-muted` |
| Type | `--hm-font-sans`, `--hm-font-display`, `--hm-font-mono`, `--hm-text-*`, `--hm-leading-*`, `--hm-tracking-display`, `--hm-tracking-label` |
| Space | `--hm-space-1` to `--hm-space-16` on a 4px grid |
| Radii | `--hm-radius-xs` 3, `sm` 4, `md` 6, `lg` 8, `pill` (tight, like the board) |
| Elevation | `--hm-shadow-xs`, `sm`, `md`, `lg` (warm-tinted) |
| Motion | `--hm-ease`, `--hm-duration-fast` 120ms, `--hm-duration` 200ms; all motion stops under `prefers-reduced-motion` |

Shared primitives in the same file:

- `.hm-btn`, with `--primary` (Signal), `--ink`, `--secondary`, `--ghost`, `--sm` and `--lg`
- `.hm-card`
- `.hm-pill`, with `--active` (Signal soft), `--success` and `--danger`
- `.hm-segmented`, `.hm-eyebrow`, `.hm-spinner` and `.hm-state`
- dark variants for anything placed inside `.hm-nav`

## Voice

- Plain and exact. Write like an analyst, not a pitch deck. Sentence case.
- Buttons say what happens: "Run simulation", "Set up agents", "Continue to interaction".
- Name things by what people recognise: knowledge graph, agents, report, rounds.
- Errors state what happened and don't apologise. Empty states say what to do next.
- Mono uppercase is reserved for labels and the nav. Never use it for sentences.

## Known gaps

- The focus ring is Signal, as the kit asks. On Paper it measures 2.5:1, below the 3:1
  that WCAG 2.2 asks of focus indicators. If strict compliance is needed, add a 1px Ink
  inner ring.
- Some strings in the workflow components are still hard-coded English and are not in the
  locale files yet.
