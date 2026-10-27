"""Generate a new page that already conforms to the content model.

The README claims this project makes the right way the easy way. Validation
alone does not do that: a linter that rejects your page after you have written
it has made the right way *mandatory*, which is a different and more annoying
thing. A reader who has to look up five required fields and two closed
vocabularies before writing a sentence will copy whichever existing page is
closest, inherit its mistakes, and resent the process.

So the content model ships with a generator. `docpack new` writes a page with
valid front matter and a skeleton appropriate to its Diataxis type, in the
right directory, with today's date.

The templates are not neutral. Each one encodes what that type of page owes its
reader, which is where most documentation goes wrong: a tutorial that forgets
to say what success looks like, a how-to that opens with three paragraphs of
background, an explanation that quietly turns into a reference. The headings
push back on each of those.

The test that matters is `tests/test_scaffold.py`, which generates one page of
every type and asserts the content model accepts all four. If that ever fails,
the generator and the validator have drifted apart, and the claim above is no
longer true.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from .frontmatter import AUDIENCES, DIATAXIS_TYPES

#: Where each Diataxis type lives. The directory is part of the content model,
#: not a loose convention, so the generator decides it rather than the author.
DIRECTORIES = {
    "tutorial": "tutorials",
    "how-to": "how-to",
    "reference": "reference",
    "explanation": "explanation",
}

#: The audience each type is usually for. A default, not a constraint.
DEFAULT_AUDIENCE = {
    "tutorial": "new-user",
    "how-to": "developer",
    "reference": "developer",
    "explanation": "developer",
}

TEMPLATES: dict[str, str] = {
    "tutorial": """# {title}

A tutorial has one job: a reader who starts with nothing finishes with
something that works. Say here what they will have built, in one sentence, and
how long it takes.

## Before you start

List what they need installed. Nothing else. A prerequisite that turns out to
be optional is the fastest way to lose a reader on the first screen.

## Step 1: <do the first thing>

```bash
# a command the reader can paste
```

Say what they should see. A step with no observable result is a step the reader
cannot tell they completed.

## Step 2: <do the next thing>

Keep going. One outcome per step, and no choices: a tutorial is not the place
to offer three ways to do something.

## What you built

Restate what now exists and what it does. This is the payoff, and it is the
section most often skipped.

## Next

Point at the how-to guides for the real work, and at an explanation page for
the reasoning. Do not explain the reasoning here.
""",
    "how-to": """# {title}

Open with the goal, in one sentence, phrased as the thing the reader is trying
to accomplish. No background: a how-to guide assumes competence and interrupts
someone mid-task.

## <first task step>

```bash
# the command
```

## <next task step>

State what to check before moving on.

## If it does not work

The two or three failures that actually happen, and what each one means. This
section is why people come back to a page.

## Related

- Link the explanation page that covers why this works this way.
- Link the reference page for the full set of options.
""",
    "reference": """# {title}

One sentence saying what this describes and what it does not. A reference page
is consulted, never read, so it owes the reader predictable structure above
everything else.

Keep this page generated from source where that is possible. Hand-written
reference is reference that drifts.

## <Interface, type, or command>

| Name | Type | Default | Description |
|---|---|---|---|
| `example` | `str` | none | What it does. |

### Returns

What comes back, and in what shape.

### Raises

Each error and the condition that produces it.

## Examples

A minimal working call. No narrative, no motivation. Those belong on an
explanation page.
""",
    "explanation": """# {title}

Explanation pages exist to answer "why is it like this", which is the question
no reference page can answer and no how-to guide should try to. State the
question in the first sentence.

## The problem

What goes wrong without this. Be concrete: a named failure beats a principle.

## The approach

What this does instead, and the mechanism that makes it work.

## What this costs

Every design decision costs something. A page that lists only the benefits
reads as marketing and gets trusted accordingly. Name the tradeoff plainly,
including the cases where a different choice would be better.

## Alternatives considered

What else was on the table and why it lost. This is the section that makes the
page worth keeping, because it answers the question a reviewer will ask in six
months when the decision is revisited.
""",
}


class ScaffoldError(ValueError):
    """Raised when a page cannot be generated."""


def slugify(title: str) -> str:
    """Turn a title into a filename stem.

    Example:
        >>> slugify("Pack a tree for RAG retrieval!")
        'pack-a-tree-for-rag-retrieval'
        >>> slugify("  Why   heading-aware  chunking  ")
        'why-heading-aware-chunking'
    """
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    if not slug:
        raise ScaffoldError(f"title {title!r} produces an empty filename")
    return slug


@dataclass(frozen=True)
class NewPage:
    """A generated page, before it is written to disk."""

    path: Path
    text: str


def render_page(
    *,
    title: str,
    diataxis: str,
    audience: str | None = None,
    summary: str | None = None,
    tags: tuple[str, ...] = (),
    today: date | None = None,
) -> str:
    """Render a conforming page as text.

    Args:
        title: Page title, used for the H1, the front matter, and the filename.
        diataxis: One of the four Diataxis types.
        audience: One of the declared audiences. Defaults per type.
        summary: One-sentence summary. A placeholder is written when omitted,
            because the field is required and an empty one fails validation.
        tags: Optional free taxonomy.
        today: Override for the `updated` date, for deterministic tests.

    Raises:
        ScaffoldError: On an unknown type or audience, reported with the valid
            options rather than just the rejection.

    Example:
        >>> text = render_page(
        ...     title="Rotate the signing key",
        ...     diataxis="how-to",
        ...     today=date(2026, 10, 26),
        ... )
        >>> print(text.split("\\n")[1])
        title: Rotate the signing key
        >>> "diataxis: how-to" in text
        True

        A value containing a colon is quoted rather than emitted raw:

        >>> text = render_page(
        ...     title="Errors: a reference",
        ...     diataxis="reference",
        ...     today=date(2026, 10, 26),
        ... )
        >>> print(text.split("\\n")[1])
        title: 'Errors: a reference'
    """
    if diataxis not in DIATAXIS_TYPES:
        raise ScaffoldError(
            f"diataxis must be one of {sorted(DIATAXIS_TYPES)}, got {diataxis!r}"
        )

    audience = audience or DEFAULT_AUDIENCE[diataxis]
    if audience not in AUDIENCES:
        raise ScaffoldError(f"audience must be one of {sorted(AUDIENCES)}, got {audience!r}")

    summary = summary or f"TODO: one sentence describing {title.lower()}."

    # Serialized with yaml rather than f-strings. The first version of this
    # function assembled the front matter by hand and produced invalid YAML the
    # moment a value contained a colon, which the default summary placeholder
    # does. Titles like "Errors: a reference" would have broken it too.
    # `tests/test_scaffold.py` caught it on the first run; quoting rules are
    # exactly the kind of thing to delegate to the parser's own library.
    front_matter: dict[str, Any] = {
        "title": title,
        "summary": summary,
        "diataxis": diataxis,
        "audience": audience,
        "updated": today or date.today(),
    }
    dumped = yaml.safe_dump(
        front_matter, sort_keys=False, default_flow_style=False, allow_unicode=True
    )

    # The tag list is dumped on its own so it renders inline, matching the
    # hand-written pages. Letting yaml choose (`default_flow_style=None`)
    # collapses the entire mapping onto one line when there are no tags to
    # nest, which is valid YAML and unreadable.
    if tags:
        inline = yaml.safe_dump(list(tags), default_flow_style=True).strip()
        dumped += f"tags: {inline}\n"

    return f"---\n{dumped}---\n\n" + TEMPLATES[diataxis].format(title=title)


def new_page(
    docs_dir: Path,
    *,
    title: str,
    diataxis: str,
    audience: str | None = None,
    summary: str | None = None,
    tags: tuple[str, ...] = (),
    today: date | None = None,
) -> NewPage:
    """Build the page and work out where it belongs.

    Does not write anything. The caller decides, so a dry run is the default
    rather than a flag.

    Raises:
        ScaffoldError: If a file already exists at the target path. Overwriting
            someone's draft to save them one keystroke is not a trade worth
            making, so there is no `--force`.
    """
    text = render_page(
        title=title,
        diataxis=diataxis,
        audience=audience,
        summary=summary,
        tags=tags,
        today=today,
    )
    path = docs_dir / DIRECTORIES[diataxis] / f"{slugify(title)}.md"
    if path.exists():
        raise ScaffoldError(f"{path} already exists")
    return NewPage(path=path, text=text)


def write_page(page: NewPage) -> Path:
    """Write a generated page to disk, creating its directory if needed."""
    page.path.parent.mkdir(parents=True, exist_ok=True)
    page.path.write_text(page.text, encoding="utf-8")
    return page.path
