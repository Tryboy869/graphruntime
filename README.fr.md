# GraphRuntime 🌐

> *Extrais l'architecture. Comprends avant d'agir. Fusionne n'importe quoi.*

**GraphRuntime** est un CLI universel qui extrait le graphe architectural de n'importe quel projet logiciel, permet à un LLM de raisonner sur ce graphe, puis génère un `runtime.json` qui connecte, modifie ou fusionne des systèmes — dans n'importe quel langage.

---

## Installation

```bash
pip install graphruntime
```

---

## Les 4 Questions Universelles

Chaque fichier, dans chaque projet, dans chaque langage répond à 4 questions :

```
→ Qu'est-ce qui entre dans ce fichier ?     (imports, dépendances)
→ Qu'est-ce qui en sort ?                   (classes, fonctions, exports)
→ Qu'est-ce qu'il appelle ?                 (dépendances internes)
→ Qui l'appelle ?                           (inféré par inversion du graphe)
```

Ces 4 questions fonctionnent sur **42 langages** : Python, TypeScript, Rust, Go, Java, C++, Terraform, SQL, GraphQL, Shell, et bien plus.

---

## Démarrage Rapide

```bash
# Extraire le graphe d'un repo local
graphruntime extract ./mon-projet

# Récupérer un graphe pré-analysé depuis le registry
graphruntime pull flask
graphruntime pull numpy

# Inspecter une architecture
graphruntime inspect graph.json

# Fusionner deux architectures
graphruntime merge graph_flask.json graph_numpy.json \
  --objectif "API REST qui traite des dataframes"

# Exécuter un runtime
graphruntime run runtime.json

# Mode objectif — l'IA choisit tout
graphruntime goal "je veux une API qui transcrit des fichiers audio en PDF"
```

---

## Commandes CLI

| Commande | Description |
|---|---|
| `extract <source>` | Extraire le graphe depuis un chemin local, GitHub, PyPI, npm, cargo |
| `pull <package>` | Récupérer un graphe pré-analysé depuis le registry |
| `inspect <graph>` | Résumé architectural lisible |
| `diff <graph_a> <graph_b>` | Diff architectural entre deux versions |
| `modify <repo>` | Modifier un repo existant guidé par le graphe |
| `create <repo>` | Créer les fichiers manquants identifiés par le graphe |
| `rewire <repo>` | Inverser ou reroutiser le flux de données entre modules |
| `merge <a> <b>` | Fusionner deux architectures en un runtime |
| `run <runtime>` | Exécuter un runtime.json |
| `watch <repo>` | Reconstruction live du graphe à chaque changement |
| `explain <graph>` | Le LLM explique l'architecture |
| `validate <repo>` | Valider l'intégrité architecturale |
| `goal "<objectif>"` | L'IA sélectionne les libs, construit et exécute tout |
| `publish <graph>` | Contribuer un graphe au registry |

---

## Registry

Le Registry GraphRuntime contient des fichiers `graph.json` pré-analysés pour les packages les plus critiques au monde.

```bash
graphruntime pull pandas
graphruntime pull kubernetes
graphruntime pull react
```

---

## Providers LLM

```bash
graphruntime config set provider groq       # par défaut
graphruntime config set provider openai
graphruntime config set provider anthropic
graphruntime config set provider ollama     # local
```

---

## Licence

MIT © GraphRuntime Contributors
