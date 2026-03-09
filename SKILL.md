# GraphRuntime SKILL v2.0

> Lu automatiquement par le CLI avant chaque appel LLM.
> **Lire entièrement avant toute action.**

---

## Ce qu'est GraphRuntime v2.0

GraphRuntime est un **agent CLI** qui accomplit des objectifs architecturaux :

```bash
graphruntime goal "app de chat temps réel multi-langages"
```

L'agent :
1. Lit le **catalogue léger** (`registry/catalogue.json`) — noms, descriptions, sources
2. **Choisit les packages** selon l'objectif
3. **Extrait les graphs en live** (`github:user/repo` → graph.json frais)
4. **Analyse chaque graph** pour comprendre l'architecture réelle
5. **Génère le runtime.json** — modules, edges, contrats, docker, CI/CD

---

## RÈGLE N°0 — La plus importante

> Le registry est un **annuaire**, pas un entrepôt de graphs pré-calculés.
> Les graphs sont **extraits en live** à la demande, jamais stockés dans le registry.
>
> Chaque entrée du catalogue contient :
> `name`, `language`, `source` (github:user/repo), `description`, `roles`
>
> Le LLM choisit depuis le catalogue, GraphRuntime extrait le graph live,
> le LLM analyse le graph frais et construit le runtime.

---

## Règles de sélection des packages

```
RÈGLE 1 : Utiliser roles[] du catalogue pour vérifier l'adéquation
RÈGLE 2 : urllib3/requests/httpx/dio/axios = http_client — JAMAIS cache
RÈGLE 3 : koin/dagger/hilt/inversify = dependency_injection — JAMAIS monitoring
RÈGLE 4 : mocha/vitest/jest/rspec/pytest/junit = testing — JAMAIS production
RÈGLE 5 : scala-js = compiler/transpiler — JAMAIS infra ou serveur
RÈGLE 6 : kotlinx.coroutines = async/concurrency — JAMAIS auth
RÈGLE 7 : Couvrir toutes les couches : frontend + api + orm + auth + infra + monitoring
RÈGLE 8 : Topologie réaliste : frontend→api→orm→db (pas de topologie en étoile)
```

---

## Format graph.json (extrait en live)

```json
{
  "meta": {
    "projet":      "fastapi",
    "langage":     "python",
    "source":      "github:tiangolo/fastapi",
    "real_roles":  ["api", "web_framework"],
    "description": "Async Python web framework for REST APIs",
    "real_entry":  "fastapi/applications.py"
  },
  "stats": {
    "fichiers_total":  48,
    "edges_total":     110,
    "noeuds_centraux": 8
  },
  "noeuds": {
    "fastapi/applications.py": {
      "type_noeud":    "central",
      "appelle":       ["routing.py", "middleware.py"],
      "est_appele_par":["__init__.py"],
      "sorties":       ["class FastAPI", "def include_router"]
    }
  },
  "patterns": [
    "central → 'fastapi/applications.py' (in=12, out=8)",
    "point_entree → 'fastapi/main.py'"
  ]
}
```

**Comment lire un graph.json :**
- `meta.real_entry` = vrai entry point (utiliser comme entry_point dans le runtime)
- `meta.real_roles` = rôles réels du package
- `stats.edges_total` élevé = architecture riche, bien connectée
- `type_noeud: central` = nœud critique, cœur de l'architecture
- `type_noeud: point_entree` = point d'entrée externe — c'est l'entry_point

---

## Format runtime.json

```json
{
  "meta": {
    "objective":    "description de l'objectif",
    "version":      "1.0.0",
    "packages":     ["pkg_a", "pkg_b"],
    "generated_by": "graphruntime goal v2.0"
  },
  "modules": {
    "module_id": {
      "package":     "pkg_name",
      "language":    "python",
      "role":        "api",
      "entry_point": "src/main.py",
      "port":        8000,
      "exposes":     {"GET /items": "returns list of items"},
      "consumes":    {"db_module": "SQL queries via ORM"},
      "env_vars":    ["DATABASE_URL", "SECRET_KEY"],
      "dockerfile":  "python:3.12-slim"
    }
  },
  "edges": [
    {
      "from": "frontend", "to": "api",
      "type": "http", "contract": "JSON REST",
      "auth": "jwt"
    }
  ]
}
```

---

## Commandes CLI v2.0

```bash
# Mode agent — l'IA fait tout
graphruntime goal "<objectif>"
  → charge catalogue → choisit packages → extrait graphs live → runtime.json

# Extraction live (tout type de source)
graphruntime extract github:user/repo
graphruntime extract pip:fastapi
graphruntime extract npm:express
graphruntime extract cargo:tokio
graphruntime extract ./local-project

# Analyse d'un graph extrait
graphruntime inspect graph.json
graphruntime explain graph.json

# Catalogue
graphruntime list --remote          # catalogue complet
graphruntime list --language python # filtre par langage
graphruntime list --role api        # filtre par rôle

# Fusion manuelle
graphruntime merge graph_a.json graph_b.json --objective "..."

# Config LLM
graphruntime config set provider groq|openai|anthropic|ollama
graphruntime config set model llama-3.3-70b-versatile
graphruntime config set api_key <key>
```

---

## Workflow complet pour un agent

```
ÉTAPE 0 : Lire ce SKILL.md (injecté automatiquement comme system prompt)
ÉTAPE 1 : graphruntime goal "<objectif>"
          → Le catalogue est chargé
          → LLM sélectionne les packages selon l'objectif et leurs roles[]
          → GraphRuntime extrait chaque graph en live (source = github:user/repo)
          → LLM analyse chaque graph frais (vraie compréhension architecturale)
          → LLM génère le runtime.json avec topologie réaliste
ÉTAPE 2 : Lire le runtime.json généré
ÉTAPE 3 : graphruntime run runtime.json (optionnel)
```

---

## Variables d'environnement

```bash
GRAPHRUNTIME_PROVIDER=groq
GRAPHRUNTIME_MODEL=llama-3.3-70b-versatile
GRAPHRUNTIME_API_KEY=<your_key>
GRAPHRUNTIME_GITHUB_TOKEN=<optional — augmente les rate limits>
```
