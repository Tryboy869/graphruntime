## [1.1.0-beta] — 2026-03-09

### Added
- `graphruntime add <source>` — Ajout de n'importe quelle source au registry local
  - Accepte : `./local`, `github:user/repo`, `pip:pkg`, `npm:pkg`, `cargo:crate`, URL directe
  - Auto-détection du nom et du langage
  - Met à jour `~/.graphruntime/registry/index.json`
  - Options : `--name`, `--language`, `--domain`, `--output`, `--registry`, `--no-index`
- `graphruntime list` — Liste le registry local ou distant
  - Filtres : `--language`, `--domain`, `--custom`, `--remote`
  - Vue tableau avec nombre de nodes/edges par entrée

### Registry
- **331 packages** pré-analysés disponibles (vs 6 au lancement)
- Couverture : 22 langages × domaines (backend, ai, infra, frontend, data, tools...)
- Sources : PyPI top-downloads / npm API / crates.io API / GitHub stars
- Accès : `graphruntime list --remote` ou `graphruntime pull <package>`

### Improved
- `graphruntime pull` — Recherche dans tous les dossiers langues du registry distant
- `graphruntime config set` — Masque la clé API dans la sortie

# Changelog

All notable changes to GraphRuntime are documented here.

Format: [Semantic Versioning](https://semver.org)

---

## [Unreleased]

## [1.0.0-beta] — 2026-03-07

### Added
- Universal graph extractor — 42 languages via 4 universal questions
- CLI commands: `extract`, `pull`, `inspect`, `diff`, `explain`, `merge`, `run`
- CLI commands: `modify`, `create`, `rewire`, `watch`, `validate`, `goal`, `publish`
- Multi-provider LLM support: Groq, OpenAI, Anthropic, Ollama
- Registry structure with index.json
- SKILL.md for AI agent integration
- GitHub Actions: auto-versioning on changelog update
- GitHub Actions: registry bootstrapping on new graph acceptance
- 4 animated SVG assets for README
- Colab deployment script
