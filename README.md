# lris2

LRIS2 Instrument Control Software

## Structure

- `daemons/` – mKTL service daemons
- `gui/` – Graphical interfaces (`slitmaskgui`, `demo`)
- `scripts/` – AIT and utility scripts
- `src/driver/` – Hardware driver submodules
- `tests/` – Unit tests

## Quick start

```bash
# 1) Clone
git clone <repo-url>
cd lris2

# 2) Make sure submodule URLs are in sync
git submodule sync --recursive
git submodule update --init --recursive

# 3) Install the package for development
pip install -U pip
pip install -e ".[dev]"
```

## Submodules

This repo uses submodules under `src/driver/`:

| Submodule | Path | Import |
|-----------|------|--------|
| coo-ethercat | `src/driver/coo_ethercat` | `lris2.driver.coo_ethercat` |
| lris2-csu | `src/driver/lris2_csu` | `lris2.driver.lris2_csu` |
| sunpower | `src/driver/sunpower` | `lris2.driver.sunpower` |

### Pull the submodules

```bash
git submodule sync --recursive
git submodule update --init --recursive
```

### Update to the latest on a tracked branch (e.g., main)

> Only do this if you intend to move submodule pointers and commit them.

```bash
# One-off refresh to submodules' tracked branches
git submodule update --remote --merge --recursive

# Record updated pointers in parent repo
git add .gitmodules .
git commit -m "Update submodules to latest on main"
```

## Testing

Tests mirror the `src/` layout under `tests/`.

To run tests from the project root:

```bash
pytest
```

## Contributing

1. Create a feature branch.
2. Include tests for new behavior.
3. Run `pytest` before opening a PR.