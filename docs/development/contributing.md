# Contributing to sinpapel

Thanks for your interest in contributing! This document describes the development
workflow and the expectations for pull requests.

## Code of Conduct

This project adopts the [Contributor Covenant 2.1](CODE_OF_CONDUCT.md). By
participating you agree to abide by its terms.

## Development Setup

```bash
git clone <repository-url>
cd sinpapel

python3 -m venv .venv
source .venv/bin/activate

pip install -e ".[dev]"
```

Run the test suite:

```bash
python -m pytest tests/ -q
```

The suite must remain green before any pull request is merged. Current
baseline: **272 passing tests**.

## Development Workflow

1. Create a feature branch off `main`:
   ```bash
   git checkout -b feat/<short-description>
   ```
2. Make focused commits. Use [Conventional Commits](https://www.conventionalcommits.org/):
   - `feat:` new feature
   - `fix:` bug fix
   - `refactor:` code change that neither fixes a bug nor adds a feature
   - `docs:` documentation only
   - `test:` adding or correcting tests
   - `chore:` tooling, build, CI
   - `ci:` CI configuration only
3. Run the test suite locally before pushing.
4. Open a pull request against `main` with a clear description and a reference
   to any related issue.

## Sign Your Work (DCO)

We use the [Developer Certificate of Origin](https://developercertificate.org/)
instead of a CLA. Every commit must be signed off:

```bash
git commit -s -m "feat: add ..."
```

Sign-off adds the line `Signed-off-by: Your Name <you@example.com>` to the
commit message. By signing off, you certify that you have the right to
contribute the change under the project license (GPL-3.0-or-later).

## Pull Request Checklist

- [ ] Tests pass locally (`python -m pytest tests/ -q`).
- [ ] New behavior covered by tests.
- [ ] `CHANGELOG.md` updated under `## [Unreleased]` when the change is
      user-visible.
- [ ] Commits follow Conventional Commits and are signed off (`-s`).
- [ ] Documentation (`docs/USAGE.md` and `docs/USAGE.es.md`) updated when
      public APIs or settings change.
- [ ] No institutional or third-party trademark references introduced
      anywhere in the codebase, README, or docs.

## Reporting Bugs

Open an issue against the project repository. Include:

- sinpapel version (`python -c "import sinpapel; print(sinpapel.__version__)"`).
- Python and Django versions.
- A minimal reproduction (model definition + the failing call).
- The full traceback.

## Reporting Security Vulnerabilities

Please **do not** open a public issue for security reports. Email
`jadrian.s@gmail.com` privately with a description and reproduction steps. You
will receive an acknowledgement within seven days.

## License

By contributing, you agree that your contributions will be licensed under the
GNU General Public License v3.0 or later, the same license as the rest of the
project.
