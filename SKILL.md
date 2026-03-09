# GraphRuntime SKILL v2.0

> Ce fichier est lu par tout LLM ou agent IA avant toute action sur GraphRuntime.
> **Lire entièrement avant d'écrire la moindre ligne de code ou de choisir un package.**

---

## Ce que je suis

GraphRuntime est un CLI Python qui :
1. **Extrait** le graphe architectural de n'importe quel projet/package (graph.json)
2. **Analyse** ce graphe pour comprendre l'architecture (noeuds, edges, patterns)
3. **Fusionne** plusieurs graphes via raisonnement LLM
4. **Génère** un `runtime.json` qui connecte et orchestre les systèmes

---

## RÈGLE FONDAMENTALE N°0 — La plus importante

> **Chaque fichier `.json` dans le registry EST le résultat de l'analyse
> architecturale du package qui porte son nom.**

```
registry/python/flask.json       → graphe architectural du package Flask (Python web framework)
registry/javascript/react.json   → graphe architectural du package React (UI library)
registry/kotlin/koin.json        → graphe architectural du package Koin (DI framework)
registry/infra/prometheus.json   → graphe architectural de Prometheus (metrics system)
```

Le LLM doit utiliser **son propre savoir sur le package** (Flask = web framework,
Koin = DI, urllib3 = HTTP client...) pour comprendre le rôle du graph.json —
et non pas tenter de déduire le rôle depuis les noms de fichiers internes du graph.

---

## Règles Fondamentales

```
RÈGLE 0 : Le nom du fichier JSON = nom du package réel. Utiliser tes connaissances
          sur ce package pour comprendre son rôle. koin.json = Koin = DI framework.
RÈGLE 1 : Toujours lire index.json AVANT de choisir des packages. Il contient
          "description" et "real_roles" pour chaque entrée.
RÈGLE 2 : Toujours vérifier que le rôle demandé correspond aux "real_roles" du package.
          Ne jamais assigner urllib3 comme "cache" — c'est un HTTP client.
RÈGLE 3 : Extraire/pull les graphs AVANT de générer un runtime.
RÈGLE 4 : Analyser chaque graph SÉPARÉMENT avant de fusionner.
RÈGLE 5 : Identifier les interfaces compatibles entre les graphs.
RÈGLE 6 : Générer le runtime.json en fonction de l'objectif précis.
RÈGLE 7 : Valider la cohérence des edges. Ne pas tout connecter sur un seul nœud.
RÈGLE 8 : Ne jamais lire le code source brut — utiliser uniquement le graphe.
```

---

## Format index.json — Champs sémantiques (v1.1+)

Depuis v1.1.0-beta, chaque entrée de `registry/index.json` contient :

```json
{
  "name":        "flask",
  "language":    "python",
  "nodes":       120,
  "edges":       87,
  "real_roles":  ["api", "web_framework", "http_server"],
  "anti_roles":  ["frontend", "orm", "monitoring", "cache"],
  "description": "Lightweight Python WSGI web framework for REST APIs",
  "real_entry":  "src/flask/app.py",
  "integrates_with": ["gunicorn", "sqlalchemy", "redis", "celery"]
}
```

**Pour choisir un package pour un rôle donné :**
1. Filtrer `index.json` sur `real_roles` contenant le rôle voulu
2. Vérifier que le rôle n'est PAS dans `anti_roles`
3. Utiliser `real_entry` comme entry point — jamais un fichier de test

---

## Format graph.json — Champs meta enrichis (v1.1+)

```json
{
  "meta": {
    "projet":       "flask",
    "langage":      "python",
    "schema":       "universal-graph-extractor v3.0",
    "real_roles":   ["api", "web_framework", "http_server"],
    "anti_roles":   ["frontend", "orm", "monitoring", "cache"],
    "description":  "Lightweight Python WSGI web framework for REST APIs",
    "real_entry":   "src/flask/app.py",
    "integrates_with": ["gunicorn", "sqlalchemy", "redis", "celery"]
  },
  "stats": {
    "fichiers_total":  24,
    "edges_total":     106,
    "noeuds_centraux": 11
  },
  "noeuds": {
    "src/flask/app.py": {
      "fichier":       "src/flask/app.py",
      "langage":       "python",
      "lignes":        150,
      "entrees":       ["flask", "json", "os"],
      "sorties":       ["class Flask", "def create_app"],
      "appelle":       ["helpers.py", "config.py"],
      "est_appele_par":["__init__.py"],
      "type_noeud":    "central|feuille|point_entree|hub|standard"
    }
  },
  "edges": [
    {"de": "app.py", "vers": "helpers.py", "type": "interne|circulaire|externe"}
  ],
  "patterns": [
    "central → 'app.py' (in=8, out=5)",
    "point_entree → 'src/flask/app.py'"
  ]
}
```

---

## Déduire le rôle réel d'un package depuis son nom

Si `real_roles` n'est pas encore dans les métadonnées, utiliser cette table :

| Pattern de nom | Rôle probable | PAS ce rôle |
|---|---|---|
| `*react*`, `*vue*`, `*angular*`, `*svelte*` | frontend, ui_framework | backend, orm |
| `*express*`, `*fastapi*`, `*flask*`, `*django*`, `*spring*`, `*ktor*` | api, web_framework | frontend, monitoring |
| `*sqlalchemy*`, `*mybatis*`, `*exposed*`, `*prisma*`, `*hibernate*` | orm, database | frontend, monitoring |
| `*prometheus*`, `*grafana*`, `*datadog*`, `*opentelemetry*` | monitoring, metrics | api, orm, auth |
| `*kubernetes*`, `*docker*`, `*traefik*`, `*nginx*`, `*ansible*` | infra, orchestration | frontend, orm |
| `*pytorch*`, `*tensorflow*`, `*langchain*`, `*transformers*` | ai, ml_framework | frontend, orm, auth |
| `*redis*`, `*memcached*` | cache, key_value_store | frontend, api |
| `*kafka*`, `*rabbitmq*`, `*celery*`, `*sidekiq*` | queue, message_broker | frontend, orm |
| `*jwt*`, `*oauth*`, `*passport*`, `*keycloak*`, `*cryptography*` | auth, security | frontend, orm |
| `*urllib3*`, `*requests*`, `*httpx*`, `*dio*`, `*axios*` | http_client | cache, api, auth |
| `*koin*`, `*dagger*`, `*spring-di*`, `*inversify*` | dependency_injection | monitoring, auth |
| `*mocha*`, `*jest*`, `*pytest*`, `*rspec*`, `*junit*` | testing | production_role |
| `*webpack*`, `*vite*`, `*esbuild*`, `*rollup*` | build_tool | production_role |

---

## Format runtime.json

```json
{
  "meta": {
    "app":        "nom-de-l-app",
    "version":    "1.0.0",
    "objective":  "description de l'objectif",
    "packages":   ["pkg_a", "pkg_b", "pkg_c"]
  },
  "modules": {
    "module_id": {
      "package":     "pkg_name",
      "language":    "python|javascript|...",
      "role":        "frontend|backend|orm|...",
      "entry_point": "chemin/vers/vrai/entry.py",
      "port":        8000,
      "exposes":     {"GET /items": "returns list of items"},
      "consumes":    {"db_module": "SQL queries via ORM"},
      "env_vars":    ["DATABASE_URL", "SECRET_KEY"],
      "dockerfile":  "python:3.12-slim"
    }
  },
  "edges": [
    {
      "from":     "frontend",
      "to":       "api",
      "type":     "http",
      "contract": "JSON REST API",
      "auth":     "jwt"
    }
  ],
  "infrastructure": {
    "gateway":    "traefik",
    "secrets":    "Kubernetes Secrets + Vault",
    "ci_cd":      "GitHub Actions",
    "monitoring": "Prometheus + Grafana"
  },
  "risks": [
    {"risk": "...", "severity": "high|medium|low", "mitigation": "..."}
  ],
  "quickstart": ["step 1", "step 2", "step 3"]
}
```

**Règles pour les edges :**
- Un edge `A → B` signifie : A appelle B (A dépend de B)
- Ne pas créer de topologie en étoile (tout → api) sans justification
- Une architecture réaliste a au moins 3 niveaux : frontend → api → db
- Les edges monitoring/infra sont généralement unilatéraux (api → prometheus, pas l'inverse)

---

## Commandes CLI v1.1.0

```bash
# Extraction
graphruntime extract <source>
  sources: ./local | github:user/repo | pip:package | npm:package | cargo:package

# Registry
graphruntime pull <package>          # graph pré-analysé depuis GitHub
graphruntime list                    # liste le registry local
graphruntime list --remote           # liste les 474 packages du registry public
graphruntime list --language python  # filtre par langage
graphruntime add <source>            # ajoute n'importe quelle source au registry local
graphruntime publish <graph.json>    # contribue au registry via PR

# Analyse
graphruntime inspect <graph.json>    # résumé lisible
graphruntime diff <a.json> <b.json>  # diff architectural
graphruntime explain <graph.json>    # explication LLM

# Modification
graphruntime modify <repo> --instruction "..."
graphruntime create <repo> --missing "description"
graphruntime rewire <repo> --from "a→b" --to "b→a"

# Fusion
graphruntime merge <a.json> <b.json> --objective "..."  → runtime.json

# Exécution
graphruntime run <runtime.json>

# Surveillance
graphruntime watch <repo> --llm

# Validation
graphruntime validate <repo> --before <graph_before.json>

# Mode objectif (IA pilote tout)
graphruntime goal "<objectif en langage naturel>"

# Configuration
graphruntime config set provider groq|openai|anthropic|ollama
graphruntime config set model llama-3.3-70b-versatile
graphruntime config set api_key <key>
```

---

## Workflow LLM — Construire une chimère full-stack

```
ÉTAPE 0 : Lire SKILL.md (ce fichier) en entier
ÉTAPE 1 : Charger index.json — filtrer sur real_roles pour chaque couche voulue
ÉTAPE 2 : Vérifier anti_roles — éliminer les packages inadaptés
ÉTAPE 3 : Pull les graph.json des packages sélectionnés
ÉTAPE 4 : Lire meta.real_entry de chaque graph → c'est le vrai entry point
ÉTAPE 5 : Construire le runtime.json avec une topologie à au moins 3 niveaux
ÉTAPE 6 : Vérifier : pas de topologie en étoile, auth sur les edges sensibles
```

---

## Registry — Structure v1.1

```
registry/
├── index.json              ← catalogue complet (474 packages, real_roles, descriptions)
├── python/                 ← 20 packages (flask, fastapi, langchain, numpy...)
├── javascript/             ← 20 packages (react, next, express, socket.io...)
├── rust/                   ← 20 packages (syn, serde, tokio...)
├── go/                     ← 20 packages
├── java/                   ← 20 packages (spring-boot, mybatis-plus...)
├── kotlin/                 ← 20 packages (ktor, exposed, koin...)
├── scala/                  ← 20 packages (akka, spark, finagle...)
├── infra/                  ← 20 packages (kubernetes, prometheus, grafana, traefik...)
├── ai/                     ← 20 packages (pytorch, tensorflow, langchain, ollama...)
└── ... 14 autres langages
```

---

## Types de Noeuds — Signification

| Type | Signification | Action recommandée |
|---|---|---|
| `central` | Appelé par 3+ fichiers ET appelle 2+ fichiers | Modifier avec précaution |
| `hub` | Appelé par >20% des fichiers | Ne jamais supprimer |
| `feuille` | Appelé par 3+ fichiers, n'appelle rien | Peut être remplacé |
| `point_entree` | Pas de dépendants, appelle 2+ fichiers | Vrai entry point externe |
| `standard` | Connexions normales | Modification libre |

---

## Variables d'Environnement

```bash
GRAPHRUNTIME_PROVIDER=groq
GRAPHRUNTIME_MODEL=llama-3.3-70b-versatile
GRAPHRUNTIME_API_KEY=<your_key>
GRAPHRUNTIME_REGISTRY=https://raw.githubusercontent.com/tryboy869/graphruntime/main/registry
GRAPHRUNTIME_GITHUB_TOKEN=<optional_for_private_repos>
```
