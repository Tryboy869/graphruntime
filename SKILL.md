# GraphRuntime SKILL

> Ce fichier permet à n'importe quel LLM ou agent IA de comprendre et piloter GraphRuntime.

## Ce que je suis

GraphRuntime est un CLI Python qui :
1. **Extrait** le graphe architectural de n'importe quel projet/package
2. **Analyse** ce graphe pour comprendre l'architecture (noeuds, edges, patterns)
3. **Fusionne** plusieurs graphes via raisonnement LLM
4. **Génère** un `runtime.json` qui connecte et exécute les systèmes

## Règles Fondamentales pour un LLM

```
RÈGLE 1 : Toujours extraire/pull les graphes AVANT de générer un runtime
RÈGLE 2 : Analyser chaque graphe SÉPARÉMENT pour comprendre l'architecture
RÈGLE 3 : Identifier les interfaces compatibles entre les graphes
RÈGLE 4 : Générer le runtime.json en fonction de l'objectif précis
RÈGLE 5 : Valider la cohérence des edges avant d'exécuter
RÈGLE 6 : Ne jamais lire le code source brut — utiliser uniquement le graphe
```

## Format graph.json

```json
{
  "meta": {
    "projet": "nom-du-projet",
    "langage": "python|typescript|rust|go|...",
    "schema": "universal-graph-extractor v3.0"
  },
  "stats": {
    "fichiers_total": 24,
    "edges_total": 106,
    "noeuds_centraux": 11
  },
  "noeuds": {
    "chemin/fichier.py": {
      "fichier": "chemin/fichier.py",
      "langage": "python",
      "lignes": 150,
      "entrees": ["flask", "json", "os"],
      "sorties": ["class App", "def create_app"],
      "appelle": ["helpers.py", "config.py"],
      "est_appele_par": ["__init__.py", "tests/test_app.py"],
      "type_noeud": "central|feuille|point_entree|hub|standard"
    }
  },
  "edges": [
    {"de": "app.py", "vers": "helpers.py", "type": "interne|circulaire|externe"}
  ],
  "patterns": [
    "central → 'app.py' (in=8, out=5)",
    "feuille → 'constants.py' (in=12)",
    "circulaire → 3 cycles détectés"
  ]
}
```

## Format runtime.json

```json
{
  "meta": {
    "nom": "nom-du-runtime",
    "objectif": "description de l'objectif",
    "langages": ["python", "javascript"]
  },
  "modules": {
    "nom_module": {
      "langage": "python|javascript|rust|go|...",
      "role": "description du rôle",
      "entree_format": {"champ": "type"},
      "sortie_format": {"champ": "type"},
      "source_graph": "graph_source.json"
    }
  },
  "edges": [
    {
      "de": "module_a",
      "vers": "module_b",
      "format": {"data": "object"},
      "type": "pipe|http|subprocess|grpc"
    }
  ],
  "entree": "premier_module",
  "sortie": "dernier_module"
}
```

## Commandes CLI

```bash
# Extraction
graphruntime extract <source>
  sources: ./local | github:user/repo | pip:package | npm:package | cargo:package

# Registry
graphruntime pull <package>          # récupère graph pré-analysé
graphruntime publish <graph.json>    # contribue au registry

# Analyse
graphruntime inspect <graph.json>    # résumé lisible
graphruntime diff <a.json> <b.json>  # diff architectural
graphruntime explain <graph.json>    # explication LLM

# Modification
graphruntime modify <repo> --instruction "..."
graphruntime create <repo> --missing "description du fichier manquant"
graphruntime rewire <repo> --from "a→b" --to "b→a"

# Fusion
graphruntime merge <a.json> <b.json> --objective "..."  → runtime.json

# Exécution
graphruntime run <runtime.json>

# Surveillance
graphruntime watch <repo> --llm groq

# Validation
graphruntime validate <repo> --before <graph_before.json>

# Mode objectif (IA pilote tout)
graphruntime goal "<objectif en langage naturel>"

# Configuration LLM
graphruntime config set provider groq|openai|anthropic|ollama
graphruntime config set model llama-3.3-70b-versatile
graphruntime config set api_key <key>
```

## Workflow Recommandé pour un Agent LLM

### Cas 1 : Comprendre un projet inconnu
```
1. graphruntime extract <repo>  →  graph.json
2. graphruntime inspect graph.json
3. graphruntime explain graph.json
→ L'agent comprend l'architecture sans lire une ligne de code
```

### Cas 2 : Modifier un comportement
```
1. graphruntime extract <repo>  →  graph.json
2. Identifier le noeud cible via inspect
3. graphruntime modify <repo> --instruction "..."
4. graphruntime validate <repo> --before graph_original.json
```

### Cas 3 : Fusionner deux packages
```
1. graphruntime pull <pkg_a>    →  graph_a.json
2. graphruntime pull <pkg_b>    →  graph_b.json
3. Analyser graph_a séparément
4. Analyser graph_b séparément
5. Identifier les interfaces compatibles
6. graphruntime merge graph_a.json graph_b.json --objective "..."
7. graphruntime run runtime.json
```

### Cas 4 : Mode objectif complet
```
1. graphruntime goal "<objectif>"
→ L'IA fait tout automatiquement :
   - Identifie les packages nécessaires
   - Pull ou extrait leurs graphs
   - Analyse les architectures
   - Génère le runtime.json
   - Exécute le système
```

## Types de Noeuds — Signification

| Type | Signification | Action recommandée |
|---|---|---|
| `central` | Appelé par 3+ fichiers ET appelle 2+ fichiers | Modifier avec précaution |
| `hub` | Appelé par >20% des fichiers | Ne jamais supprimer |
| `feuille` | Appelé par 3+ fichiers, n'appelle rien | Peut être remplacé facilement |
| `point_entree` | Pas de dépendants, appelle 2+ fichiers | Point de départ du pipeline |
| `standard` | Connexions normales | Modification libre |

## Patterns Architecturaux — Interprétation

```
circulaire → Dépendances cycliques — fragilité potentielle
central    → Coeur de l'architecture — modifier en dernier
feuille    → Primitive stable — bonne cible pour extraction
pont       → Seul lien entre deux clusters — risque si supprimé
```

## Registry — Structure

```
registry/
├── index.json              ← catalogue complet avec métadonnées
├── python/
│   ├── flask@3.1.json
│   ├── pandas@2.2.json
│   └── ...
├── javascript/
├── rust/
├── go/
├── infra/
└── ai/
```

## Critères d'Admission au Registry

Un package est admis si :
- Stars GitHub ≥ 10 000
- Téléchargements ≥ 100K/semaine
- Âge ≥ 2 ans OU sponsor institutionnel
- Dernier commit < 6 mois

## Variables d'Environnement

```bash
GRAPHRUNTIME_PROVIDER=groq
GRAPHRUNTIME_MODEL=llama-3.3-70b-versatile
GRAPHRUNTIME_API_KEY=<your_key>
GRAPHRUNTIME_REGISTRY=https://raw.githubusercontent.com/tryboy869/graphruntime/main/registry
GRAPHRUNTIME_GITHUB_TOKEN=<optional_for_private_repos>
```
