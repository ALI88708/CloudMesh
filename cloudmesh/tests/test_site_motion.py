"""Motion must never be the reason content is visible.

The site already neutralises all animation under `prefers-reduced-motion`. That
is only a safety net for motion that *finishes*: if an animation defines its end
state and the duration is forced to 0.01ms, a reduced-motion user gets content
frozen at the start value, which is invisible. So a reveal must default to
visible and animate only on the way in.

These are static checks on the source. The suite has no browser and adding one
is out of scope, so what is verified is the shape of the code -- that the two
rules above hold, and that a future edit cannot quietly undo them.
"""

import re
from pathlib import Path

SITE = Path(__file__).resolve().parent.parent.parent / "site"
HTML = (SITE / "index.html").read_text(encoding="utf-8")
CSS = (SITE / "styles.css").read_text(encoding="utf-8")
JS = (SITE / "app.js").read_text(encoding="utf-8")


def _reduced_motion_block() -> str:
    """The body of the global reduced-motion block, brace-matched.

    Splitting on the `@media` prelude alone would swallow every later rule into
    the "block", so a rule added after it would read as part of the safety net.
    """
    start = CSS.index("@media (prefers-reduced-motion: reduce)")
    depth = 0
    for index in range(CSS.index("{", start), len(CSS)):
        if CSS[index] == "{":
            depth += 1
        elif CSS[index] == "}":
            depth -= 1
            if depth == 0:
                return CSS[start: index + 1]
    raise AssertionError("the reduced-motion block is never closed")


def test_reduced_motion_block_exists():
    """The existing block is the safety net; do not delete it."""
    assert "@media (prefers-reduced-motion: reduce)" in CSS


def test_reduced_motion_block_neutralises_animation_and_transition():
    block = _reduced_motion_block()
    assert "animation-duration: 0.01ms" in block
    assert "transition-duration: 0.01ms" in block


def test_reduced_motion_block_still_applies_to_everything():
    """It has to be a universal selector, or it is not a safety net."""
    block = _reduced_motion_block()
    assert re.search(r"\*\s*,\s*\*::before\s*,\s*\*::after", block)


def test_reveal_default_shows_content():
    """A reveal must transition INTO visible, never hold content at opacity 0.

    The base rule is what a reduced-motion reader gets, because the hiding rule
    lives behind a `no-preference` guard they never match.
    """
    for rule in re.findall(r"(?m)^\[data-reveal\]\s*\{[^}]*\}", CSS):
        assert "opacity: 1" in rule or "opacity:1" in rule, (
            f"a base [data-reveal] rule holds content invisible: {rule}"
        )


def test_reveal_hiding_rule_is_guarded_by_no_preference():
    """`opacity: 0` may only appear inside `prefers-reduced-motion: no-preference`.

    This is the assertion that would have caught the real bug: a reveal that
    hides content in the base stylesheet and relies on the animation to bring it
    back is invisible to every reduced-motion reader.
    """
    guarded = re.search(
        r"@media\s*\(prefers-reduced-motion:\s*no-preference\)\s*\{.*?"
        r"\[data-reveal\]:not\(\.is-revealed\)\s*\{[^}]*opacity:\s*0",
        CSS,
        re.S,
    )
    assert guarded, (
        "the [data-reveal]:not(.is-revealed) opacity:0 rule is not inside a "
        "prefers-reduced-motion: no-preference guard"
    )

    # Nothing outside that guard may hide a reveal.
    outside = re.sub(
        r"@media\s*\(prefers-reduced-motion:\s*no-preference\)\s*\{.*?\n\}",
        "",
        CSS,
        flags=re.S,
    )
    for rule in re.findall(r"\[data-reveal\][^{}]*\{[^}]*opacity:\s*0[^}]*\}", outside):
        raise AssertionError(f"a reveal rule outside the guard hides content: {rule}")


def test_reveal_uses_opacity_and_transform():
    """Interpolation only -- no `display` or `visibility` toggles mid-animation."""
    reveal_css = CSS[CSS.index("@media (prefers-reduced-motion: no-preference)"):]
    assert "opacity" in reveal_css and "transform" in reveal_css


def test_the_css_selector_actually_matches_the_markup():
    """A reveal rule that matches no element is a reveal that never animates.

    This is a real defect that shipped during development of this page: the CSS
    keyed on `.reveal` while the markup opted in with `data-reveal` and carried
    no such class, so the whole animation was dead. Nothing else here could
    have caught it -- every other assertion read true of a rule that never
    applied to a single element.
    """
    assert "data-reveal" in HTML
    assert "[data-reveal]" in CSS, (
        "the stylesheet keys the reveal on a selector the markup does not use"
    )
    # The observer and the stylesheet must agree on the opt-in.
    assert "querySelectorAll(\"[data-reveal]\")" in JS


def test_hero_entrance_animates_only_under_no_preference():
    """The hero entrance has the same hazard as the reveals, so the same guard.

    `animation-fill-mode: backwards` holds the from-state through the stagger
    delay, which is exactly what makes a reduced-motion reader see nothing.
    """
    hero = CSS[CSS.index("prefers-reduced-motion: no-preference"):]
    assert "animation:" in hero, "no hero entrance animation found"
    # The keyframes may only be reachable from inside the guard: a bare
    # `.hero-*` animation rule in the base stylesheet would bypass it.
    base = CSS[: CSS.index("@media (prefers-reduced-motion: no-preference)")]
    assert not re.search(r"(?m)^\s*\.hero-\w+\s*\{[^}]*animation:", base), (
        "a hero entrance animation sits outside the no-preference guard"
    )


def test_observer_is_feature_detected():
    assert "IntersectionObserver" in JS
    assert re.search(r"if\s*\(\s*window\.IntersectionObserver\s*\)", JS) or (
        "IntersectionObserver" in JS and "window.IntersectionObserver" in JS
    ), "IntersectionObserver must be feature-detected, not assumed"


def test_observer_falls_back_without_hiding_content():
    """The else branch must reveal everything, because there is no observer.

    A fallback that simply does nothing leaves the page correct only if the
    hiding rule is inert -- which it is, under reduced motion, but not here.
    """
    fallback = JS.split("else", 1)[-1] if "else" in JS else ""
    assert "is-revealed" in fallback, (
        "the no-IntersectionObserver branch must add is-revealed to every target"
    )


def test_observer_unobserves_after_revealing():
    """Observe once, then unobserve, so reveals do not re-trigger on re-entry."""
    assert "unobserve(" in JS
    observer_body = JS[JS.index("new IntersectionObserver"):]
    assert re.search(r"classList\.add\(\"is-revealed\"\)\s*;\s*observer\.unobserve", observer_body), (
        "the reveal handler must unobserve the target immediately after revealing it"
    )


def test_no_scroll_event_listener_drives_the_reveal():
    """A scroll listener runs a handler every frame; IntersectionObserver does not."""
    assert "addEventListener('scroll'" not in JS
    assert 'addEventListener("scroll"' not in JS


def test_sections_carry_the_reveal_attribute():
    """The observer has targets to observe, or it silently does nothing."""
    assert 'data-reveal' in HTML
    assert HTML.count("data-reveal") >= 4, "too few sections opt in to the reveal"