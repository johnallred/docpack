"""STYLE.md is the human half of the style guide; the Vale rules are the other.

The two drift apart exactly the way any copied fact does, so this holds them
together: every rule has a row at its real level, every term and hedge word
the rules name is listed, and no substitution swaps a word for itself. That
last case happened. A bulk spelling change rewrote both sides of the Diataxis
rule, and it caught nothing for weeks while CI stayed green.
"""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
RULES = ROOT / "styles" / "Showcase"
GUIDE = (ROOT / "STYLE.md").read_text(encoding="utf-8")


def rule(name: str) -> dict:
    return yaml.safe_load((RULES / f"{name}.yml").read_text(encoding="utf-8"))


def test_every_rule_has_a_row_at_its_real_level():
    for path in sorted(RULES.glob("*.yml")):
        level = rule(path.stem)["level"]
        assert f"| `{path.stem}` | {level} |" in GUIDE, f"{path.stem} ({level}) is not in STYLE.md"


def test_every_term_is_listed_the_right_way_round():
    for wrong, right in rule("Terms")["swap"].items():
        assert f"| {right} | {wrong} |" in GUIDE, f"{wrong} -> {right} is not in STYLE.md"


def test_no_term_swaps_a_word_for_itself():
    same = [k for k, v in rule("Terms")["swap"].items() if k == v]
    assert not same, f"these substitutions can never fire: {same}"


def test_every_hedge_word_is_listed():
    for token in rule("Hedging")["tokens"]:
        assert token in GUIDE, f"hedge word {token!r} is not in STYLE.md"


def test_every_heading_exception_is_listed():
    for word in rule("HeadingCase")["exceptions"]:
        assert word in GUIDE, f"heading exception {word!r} is not in STYLE.md"
