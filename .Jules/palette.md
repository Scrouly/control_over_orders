## 2026-02-26 - [Sidebar Accessibility and Keyboard Navigation]
**Learning:** Collapsible sidebar menus using `div` with `onclick` are not keyboard-accessible. Converting them to `<button>` elements and adding appropriate ARIA attributes (`aria-expanded`, `aria-controls`) significantly improves accessibility for keyboard and screen reader users.
**Action:** Always use semantic `<button>` for collapsible elements and ensure ARIA attributes are updated via JavaScript. Add `title` for tooltips and `aria-label` for icon-only buttons.
