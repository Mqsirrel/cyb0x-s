# Contributing

Thanks for helping improve GLACIS. This is an exam-companion project — keep
changes small, tested, and compliant with [docs/EXAM_COMPLIANCE.md](docs/EXAM_COMPLIANCE.md).

## Setup

```bash
uv sync --all-extras
```

## Code Quality & Linting

```bash
uv run ruff check src/ tests/ scripts/ dev/
```

## Tests

Two tiers, both parallelized with pytest-xdist:

```bash
uv run pytest -m fast -n auto   # fast tier: no TUI rendering
uv run pytest -n auto           # full suite, including TUI tests
```

Mark new unit tests with `@pytest.mark.fast`; TUI/rendering tests stay in the
default tier. All code must pass `ruff check src/ tests/ scripts/ dev/` cleanly.

## TUI changes

The project uses a screenshot-driven review loop:

1. `uv run python dev/screentext.py` — dump the current screen as text
2. `uv run python dev/screenshot.py` — render PNG previews into `dev/previews/`
3. Record notable UI decisions in `docs/UI_UX_REVIEW.md`

Attach a preview to any PR that changes layout, theme, or keybindings.

## Commits

Conventional commits with a scope, matching the existing history:
`feat(tui): ...`, `fix(store): ...`, `perf(search): ...`, `docs: ...`,
`test: ...`, `style(tui): ...`.

## Pull requests

- One concern per PR
- Tests for behavior changes
- Run the exam-compliance checklist in `docs/EXAM_COMPLIANCE.md` before
  requesting review
