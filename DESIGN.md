# Manju Library — design system

**Idea: a reading room.** Warm paper, a deep green like the classic library reading lamp,
and a little brass light. Calm and focused: the interface stays quiet and lets what needs
action — a due fee, a seat ending, a reminder to send — stand out.

## Principles

1. **Calm by default, loud only for action.** Colour is spent on state and the next step,
   never on decoration. One primary action per screen.
2. **Phone first for students, keyboard fast for the desk.** Students open the portal on a
   phone; the front desk works on a laptop all day (⌘K finds any student).
3. **Words carry meaning, colour adds to it.** Every status has text or an icon too.
4. **Same thing, same look.** Every list, form, badge and number uses the shared components.

## Colour

All colours are tokens in `frontend/src/index.css` (`:root`, dark mode under
`prefers-color-scheme: dark`, and print). Components never use raw colours.

| Token | Use |
|---|---|
| `background` | Warm paper page background |
| `card` | Surfaces: cards, tables, dialogs |
| `foreground` / `muted-foreground` | Ink-green text / secondary text |
| `primary` | Library green: primary buttons, links, active navigation |
| `secondary` | Soft green tint: selected states, soft buttons |
| `accent` | Brass: the one warm highlight (active nav marker, brand glow, counts, the days-left ring) |
| `accent-ink` | Brass dark enough for text on paper (large numerals); plain `accent` is for fills and dark panels |
| `success` `warning` `destructive` | State only, always with text or an icon |
| `sidebar-*` | The deep green navigation panel |
| `chart-*` | Validated chart palette (see the data-viz notes in `AnalyticsPage`) |

Dark mode is "night study": deep green-black surfaces, paper-coloured text, a lighter
green and the same brass.

## Type

- **Fraunces** (variable serif) for page titles, the brand and the landing hero only.
- **Plus Jakarta Sans** (variable) for everything else, including all numbers.
  Large standalone numbers use proportional figures; columns use `tabular-nums`.
- Scale: page title 30/36px, section title 18px, body 14–15px, small 12–13px.
- Hindi and other scripts fall back to the system's fonts.

Both fonts are bundled with the app (no outside requests; the CSP stays `font-src 'self'`).

## Shape, depth and motion

- Radius: 10px controls, 12px small cards, 16px cards and dialogs, full for pills.
- Depth: hairline borders plus one soft shadow (`shadow-card`); dialogs, menus and the
  membership pass use `shadow-float`. No heavy shadows.
- Gradients only in three brand moments: the sign-in panel, the landing page, and the
  student's membership pass (the "reading lamp" glow). Never on working screens.
- Motion: 150–220ms ease-out on hover, press and dialogs; nothing moves when the system
  asks for reduced motion.

## Components

`components/ui`: Button (variants default, secondary, outline, ghost, destructive, link,
accent; sizes sm/default/lg/icon; `loading`), Input, Select, Textarea, Label, Card,
Badge (tones with optional dot), Alert (with icon and optional title), Table, Dialog,
Spinner, Skeleton, Segmented (pressed buttons for switching a list's view), Avatar
(initials), Meter (thin share-of-a-whole bar), PageHeader, StatCard (with icon),
EmptyState (with icon and action), Pagination.

- **PageHeader** shows the menu section above the title ("Money" on Payments) on its own;
  pass `eyebrow` to replace it (the overview shows the date) and `media` for an avatar.
- **Tables** drop secondary columns on phones (`hidden sm:table-cell`) and fold the key
  facts into the name cell, instead of scrolling sideways.

Layouts: `AppShell` (staff: green sidebar with grouped navigation, ⌘K search, phone drawer;
students: header and a bottom tab bar on phones that keeps the chosen sibling), `PublicLayout`,
`AuthCard` (split brand panel and form).

## Key screens

- **Overview** greets the person, then four numbers (members, seats in use, collected today,
  dues), a "To do today" list (reminders, renewals, waiting list), renewals due this week and
  the latest payments.
- **Student home** is a membership pass: seat and timing large, a ring for the days left,
  fees beside it, then notices. Phone first.
- **Seat map** tiles show the seat, who sits there and a thin line of the library's day
  filled where it is booked. States: free, part of the day free (seat sharing), full,
  switched off (hatched); a brass "3d" pill marks a membership ending within a week. Picking
  a shift shows which seats are free in it, and a free seat admits straight into itself.

## Accessibility

Contrast at least 4.5:1 for text (3:1 for large display numerals); focus is always visible (2px ring); every icon-only
button has a label; dialogs trap focus and return it; touch targets are at least 40px on
phones; animations respect `prefers-reduced-motion`.
