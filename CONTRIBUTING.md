# Contributing

Thanks for your interest in improving `timescaledb`. This guide covers setting up
a development environment, running the tests and checks, and the release process.

By contributing you agree that your work is licensed under the project's
[MIT License](./LICENSE).

## Requirements

- Python 3.11, 3.12, 3.13, or 3.14
- **Docker** running locally (Docker Desktop, Colima, OrbStack, …). The test
  suite starts a real TimescaleDB container via
  [`testcontainers`](https://testcontainers.com/), so a working Docker daemon is
  required to run the tests.

## Development environment

Either [`uv`](https://docs.astral.sh/uv/) or a plain `venv` works. The CI uses
`uv`.

### Using uv

```bash
uv venv
source .venv/bin/activate              # Windows: .venv\Scripts\activate

# Install the package in editable mode
uv pip install -e .

# Install the dev/test tooling
uv pip install -r requirements.dev.txt
```

### Using venv + pip

```bash
python -m venv .venv
source .venv/bin/activate              # Windows: .venv\Scripts\activate

pip install -e .
pip install -r requirements.dev.txt
```

`requirements.dev.txt` pulls in `tox`, `coverage`, `pytest`, `bump2version`,
`pre_commit`, and `testcontainers[postgres]`.

## Running the test suite

The tests need **no manual database setup**; `testcontainers` starts a
throwaway TimescaleDB container and tears it down afterwards. Make sure Docker is
running first.

Run the tests directly with `pytest`:

```bash
python -m pytest tests
```

Or run them across an interpreter with `tox` (the locked dependency sets for
each Python version live in `tests/requirements/`):

```bash
# all configured interpreters (py311–py314)
tox

# a single interpreter, e.g. 3.12
tox run -f py312
```

The first run is slow because Docker pulls the TimescaleDB image; subsequent runs
reuse the cached image.

### Coverage

`tox` runs the suite under `coverage`. To combine results and view a report
(CI fails under 85%):

```bash
coverage combine
coverage report
```

### Sample projects

The [`samples/`](./samples/) directory has its own fully-tested example projects
with their own dependencies. See [`samples/README.md`](./samples/README.md) for
how to run those suites.

### Long-lived database (optional)

For manual experimentation against a persistent database instead of throwaway
containers, a `compose.yaml` is provided:

```bash
docker compose up -d
# DATABASE_URL=postgresql+psycopg://timescaledb:timescaledb@localhost:5432/timescaledb
docker compose down -v                 # stop + wipe when finished
```

## Lint and type checks

Both run in CI and should pass before opening a PR.

```bash
# flake8 (config lives in the [flake8] section of tox.ini)
flake8 src tests

# mypy (strict mode, configured in [tool.mypy] in pyproject.toml)
mypy src/timescaledb
```

Imports are sorted with `isort` (`force_single_line`, black profile); see the
`[tool.isort]` config in `pyproject.toml`. A `pre-commit` config can be installed
with `pre-commit install` if you use it.

## Pull request guidelines

- Keep PRs focused on a single change.
- Add or update tests for any behavior change; new helpers should ship with
  coverage (CI enforces an 85% floor).
- Make sure `flake8`, `mypy`, and the test suite pass locally.
- Update the `README.md` and/or `samples/` when you add or change public API.
- Do **not** bump the version in your PR; releases are cut separately (see
  below).

## Release process

Releases are published to [PyPI](https://pypi.org/project/timescaledb/) by CI
when a tag is pushed. Versioning is `MAJOR.MINOR.PATCH` and driven by
[`bump2version`](https://github.com/c4urself/bump2version) (config in
`.bumpversion.cfg`, which updates `pyproject.toml` and
`src/timescaledb/__init__.py`).

1. On `main`, bump the version. `bump2version` is configured to create the
   commit **and** the git tag automatically (`commit = True`, `tag = True`):

   ```bash
   bump2version patch     # or: minor / major
   ```

2. Push the commit and the tag:

   ```bash
   git push origin main --follow-tags
   ```

3. The `Release` workflow (`.github/workflows/workflow.yaml`) runs lint, type
   checks, and the full test matrix. When the pushed ref is a tag and everything
   passes, the `release` job builds the package with `uv build` and publishes it
   to PyPI via trusted publishing (OIDC) using
   `pypa/gh-action-pypi-publish`.

No PyPI token is needed locally; publishing happens entirely in CI.
