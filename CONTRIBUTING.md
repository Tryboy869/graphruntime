# Contributing to GraphRuntime

Thank you for your interest in contributing!

## Ways to Contribute

### 1. Add a package to the Registry

The most impactful contribution. Criteria:
- ≥ 10,000 GitHub stars
- ≥ 100,000 weekly downloads
- ≥ 2 years old OR institutional sponsor
- Last commit < 6 months

**Steps:**
```bash
pip install graphruntime
graphruntime extract pip:package-name -o registry/python/package-name.json
# or for npm:
graphruntime extract npm:package-name -o registry/javascript/package-name.json
```

Then open a PR with the new `.json` file.

### 2. Improve the extractor

Add signals for new languages in `graphruntime/extractor.py`.

### 3. Report bugs

Open an issue with:
- OS and Python version
- Command that failed
- Full error output

### 4. Improve documentation

Fix typos, add examples, translate README.

## Development Setup

```bash
git clone https://github.com/tryboy869/graphruntime
cd graphruntime
pip install -e ".[all]"
```

## Pull Request Process

1. Fork the repo
2. Create a branch: `git checkout -b feat/my-feature`
3. Commit: `git commit -m 'feat: description'`
4. Push: `git push origin feat/my-feature`
5. Open a PR

## Registry File Format

Each registry file must be a valid `graph.json` with:
- `meta.projet` — package name
- `stats.fichiers_total` ≥ 3
- `noeuds` — non-empty
- `edges` — non-empty

The CI will validate automatically on PR.
