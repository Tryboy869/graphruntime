"""
GraphRuntime GoalAgent v2.0
Agent LLM qui accomplit un objectif complet :
  1. Lit le catalogue léger
  2. Choisit les packages selon l'objectif
  3. Extrait les graphs en live (github:user/repo)
  4. Analyse chaque graph
  5. Fusionne → runtime.json
"""
import json
import re
import time
import tempfile
import shutil
import io
import zipfile
from pathlib import Path
from typing import Optional

import requests

CATALOGUE_URL = (
    "https://raw.githubusercontent.com/tryboy869/graphruntime/main"
    "/registry/catalogue.json"
)
SKILL_URL = (
    "https://raw.githubusercontent.com/tryboy869/graphruntime/main/SKILL.md"
)

# ── Skill cache ───────────────────────────────────────────────────
_skill_cache: Optional[str] = None

def load_skill() -> str:
    global _skill_cache
    if _skill_cache is not None:
        return _skill_cache
    try:
        r = requests.get(SKILL_URL, timeout=5)
        _skill_cache = r.text if r.status_code == 200 else ""
    except Exception:
        _skill_cache = ""
    return _skill_cache

def build_system_prompt() -> str:
    skill = load_skill()
    base = (
        "You are a software architect agent using GraphRuntime.\n"
        "You choose packages, analyze their architecture graphs, "
        "and generate production runtime.json files.\n\n"
    )
    if skill:
        base += f"SKILL.md (read before any action):\n{skill}\n\n"
    base += (
        "CRITICAL RULES:\n"
        "- Each package source is github:user/repo or pip:name\n"
        "- urllib3/requests/httpx = http_client — NEVER cache\n"
        "- koin/dagger = dependency_injection — NEVER monitoring\n"
        "- mocha/vitest/jest = testing — NEVER production role\n"
        "- Build topologies with at least 3 levels: frontend→api→db\n"
        "- Use real_entry from graph meta when available\n"
    )
    return base

def safe_json(text: str):
    try:
        return json.loads(text)
    except Exception:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                pass
    return None

# ── Catalogue ─────────────────────────────────────────────────────
def fetch_catalogue() -> list:
    r = requests.get(CATALOGUE_URL, timeout=15)
    return r.json().get("packages", [])

# ── Live extraction ───────────────────────────────────────────────
def extract_live(source: str, extractor) -> Optional[dict]:
    """
    Extrait le graph d'un package en live depuis sa source.
    source : github:user/repo | pip:name | npm:name | cargo:name
    """
    if source.startswith("github:"):
        full_name = source[len("github:"):]
        return _extract_github(full_name, extractor)
    elif source.startswith("pip:"):
        return _extract_pip(source[4:], extractor)
    return None

def _extract_github(full_name: str, extractor) -> Optional[dict]:
    """Télécharge le ZIP GitHub et extrait le graph."""
    url = f"https://api.github.com/repos/{full_name}/zipball/HEAD"
    headers = {}
    token = _get_github_token()
    if token:
        headers["Authorization"] = f"token {token}"
    try:
        r = requests.get(url, headers=headers, timeout=30, stream=True)
        if r.status_code != 200:
            return None
        tmp = Path(tempfile.mkdtemp())
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            z.extractall(tmp)
        subdirs = [d for d in tmp.iterdir() if d.is_dir()]
        repo_root = subdirs[0] if subdirs else tmp
        graph = extractor.extract(str(repo_root))
        graph.setdefault("meta", {})["source"] = f"github:{full_name}"
        return graph
    except Exception:
        return None
    finally:
        if 'tmp' in dir() and tmp.exists():
            shutil.rmtree(tmp, ignore_errors=True)

def _extract_pip(pkg_name: str, extractor) -> Optional[dict]:
    """Installe le package pip dans un tmp dir et extrait le graph."""
    import subprocess
    tmp = Path(tempfile.mkdtemp())
    try:
        subprocess.run(
            f"pip download {pkg_name} --no-deps -d {tmp}/dist -q",
            shell=True, timeout=30
        )
        wheels = list((tmp/"dist").glob("*.whl"))
        if wheels:
            import zipfile as zf
            with zf.ZipFile(wheels[0]) as z:
                z.extractall(tmp/"pkg")
            graph = extractor.extract(str(tmp/"pkg"))
            graph.setdefault("meta", {})["source"] = f"pip:{pkg_name}"
            return graph
    except Exception:
        return None
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

def _get_github_token() -> str:
    import os
    return os.environ.get("GRAPHRUNTIME_GITHUB_TOKEN",
                          os.environ.get("GITHUB_TOKEN", ""))

# ── Graph analysis ────────────────────────────────────────────────
def summarize_graph(graph: dict, top_n: int = 8) -> dict:
    """Résumé compact d'un graph pour le LLM — évite de saturer le contexte."""
    noeuds = graph.get("noeuds", {})
    top = sorted(
        noeuds.items(),
        key=lambda x: (
            len(x[1].get("est_appele_par", [])) +
            len(x[1].get("appelle", []))
        ),
        reverse=True,
    )[:top_n]
    return {
        "meta":     graph.get("meta", {}),
        "stats":    graph.get("stats", {}),
        "patterns": graph.get("patterns", [])[:6],
        "top_nodes": [
            {
                "path":    k,
                "type":    v.get("type_noeud"),
                "in":      len(v.get("est_appele_par", [])),
                "out":     len(v.get("appelle", [])),
                "exports": v.get("sorties", [])[:4],
            }
            for k, v in top
        ],
    }


class GoalAgent:
    """
    Agent LLM GraphRuntime v2.0

    Workflow :
      1. charge le catalogue léger
      2. LLM choisit les packages selon l'objectif
      3. extrait les graphs en live
      4. LLM analyse chaque graph
      5. LLM génère le runtime.json final
    """

    def __init__(self, client, model: str, provider: str = "groq"):
        self.client   = client
        self.model    = model
        self.provider = provider
        self.sys_prompt = build_system_prompt()

        try:
            from graphruntime.extractor import Extractor
            self.extractor = Extractor(max_files=120)
        except ImportError:
            self.extractor = None

    def _llm(self, prompt: str, max_tokens: int = 2000,
             json_mode: bool = False) -> str:
        messages = [
            {"role": "system", "content": self.sys_prompt},
            {"role": "user",   "content": prompt},
        ]
        if self.provider == "anthropic":
            kwargs = dict(
                model=self.model,
                max_tokens=max_tokens,
                system=self.sys_prompt,
                messages=[{"role": "user", "content": prompt}],
            )
            r = self.client.messages.create(**kwargs)
            return r.content[0].text.strip()
        else:
            kwargs = dict(
                model=self.model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=0.2,
            )
            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}
            r = self.client.chat.completions.create(**kwargs)
            return r.choices[0].message.content.strip()

    # ── Step 1 : sélection des packages ──────────────────────────
    def select_packages(self, objective: str, catalogue: list,
                        max_packages: int = 8) -> list:
        compact = [
            {
                "name":        p["name"],
                "language":    p["language"],
                "source":      p["source"],
                "description": p["description"],
                "roles":       p.get("roles", []),
            }
            for p in catalogue
        ]
        prompt = f"""Objective: {objective}

Available packages catalogue ({len(compact)} packages):
{json.dumps(compact, indent=2)}

Select the BEST packages to accomplish this objective.

Rules:
- Choose {max_packages} packages maximum
- Cover all required layers: frontend + backend/api + database/orm + infra/monitoring
- Each package's roles must match its function in the architecture
- Prefer packages with precise role descriptions
- Do NOT choose: urllib3/requests as cache, koin as monitoring,
  test frameworks (mocha/vitest/jest) as production components

Return ONLY valid JSON:
{{
  "objective_analysis": "What architecture this requires",
  "selected": [
    {{
      "name":           "<package name>",
      "language":       "<language>",
      "source":         "<github:user/repo or pip:name>",
      "assigned_role":  "<role in THIS architecture>",
      "why":            "<one sentence: why this package for this role>"
    }}
  ]
}}"""
        raw = self._llm(prompt, max_tokens=1500, json_mode=True)
        result = safe_json(raw)
        if result and "selected" in result:
            return result["selected"]
        return []

    # ── Step 2 : extraction live ──────────────────────────────────
    def extract_graphs(self, selected: list) -> dict:
        """
        Extrait le graph de chaque package sélectionné.
        Retourne {pkg_name: graph_dict}.
        """
        if self.extractor is None:
            return {}
        graphs = {}
        for pkg in selected:
            name   = pkg["name"]
            source = pkg.get("source", "")
            print(f"  → Extraction live : {name} ({source})", end=" ", flush=True)
            graph = extract_live(source, self.extractor)
            if graph:
                nodes = graph.get("stats", {}).get("fichiers_total", 0)
                edges = graph.get("stats", {}).get("edges_total", 0)
                print(f"✓ {nodes}n {edges}e", flush=True)
                graphs[name] = graph
            else:
                print("✗ échec extraction", flush=True)
        return graphs

    # ── Step 3 : analyse individuelle ────────────────────────────
    def analyze_graph(self, name: str, role: str,
                      graph: dict, objective: str) -> str:
        summary = summarize_graph(graph)
        prompt = f"""You extracted the architectural graph of '{name}' to use as '{role}' layer.

Objective: {objective}
Graph summary: {json.dumps(summary, indent=2)}

Answer concisely:
ENTRY_POINT: The real main entry point (NOT a test file)
EXPOSES: What APIs/interfaces/events this package exposes (max 4)
REQUIRES: What it needs from other layers (max 3)
INTEGRATION: How to integrate this into the architecture
CONCERN: One critical production concern"""
        return self._llm(prompt, max_tokens=400)

    # ── Step 4 : génération runtime ──────────────────────────────
    def generate_runtime(self, objective: str, selected: list,
                         graphs: dict, analyses: dict) -> dict:
        arch_ctx = {}
        for pkg in selected:
            name = pkg["name"]
            graph = graphs.get(name, {})
            arch_ctx[name] = {
                "language":   pkg.get("language", "?"),
                "role":       pkg.get("assigned_role", "?"),
                "why":        pkg.get("why", ""),
                "stats":      graph.get("stats", {}),
                "meta":       graph.get("meta", {}),
                "analysis":   analyses.get(name, "")[:400],
                "top_nodes":  summarize_graph(graph, top_n=3).get("top_nodes", []),
            }

        prompt = f"""Generate a production runtime.json for:
OBJECTIVE: {objective}
PACKAGES: {json.dumps([p["name"] for p in selected])}

Architecture context:
{json.dumps(arch_ctx, indent=2)}

Return ONLY valid JSON — complete production runtime:
{{
  "meta": {{
    "objective":  "{objective}",
    "version":    "1.0.0",
    "packages":   {json.dumps([p["name"] for p in selected])},
    "generated_by": "graphruntime goal v2.0"
  }},
  "modules": {{
    "<module_id>": {{
      "package":     "<name>",
      "language":    "<lang>",
      "role":        "<role>",
      "entry_point": "<real main file — NOT a test>",
      "port":        <number or null>,
      "exposes":     {{"<endpoint or event>": "<description>"}},
      "consumes":    {{"<other_module_id>": "<what it gets>"}},
      "env_vars":    ["<VAR_NAME>"],
      "dockerfile":  "<base image>"
    }}
  }},
  "edges": [
    {{
      "from":     "<module_id>",
      "to":       "<module_id>",
      "type":     "http|grpc|sql|event|websocket|import",
      "contract": "<data shape or API contract>",
      "auth":     "none|jwt|api_key|mtls"
    }}
  ],
  "infrastructure": {{
    "gateway":    "<reverse proxy or API gateway module>",
    "secrets":    "<secrets management approach>",
    "ci_cd":      "<CI/CD pipeline>",
    "monitoring": "<observability stack>"
  }},
  "risks": [
    {{"risk": "...", "severity": "high|medium|low", "mitigation": "..."}}
  ],
  "quickstart": ["step 1", "step 2", "step 3"]
}}

IMPORTANT:
- Topology must have at least 3 levels: frontend → api → db
- Do NOT route everything through one module (no star topology)
- auth edges need jwt or api_key
- entry_point must be a real source file, not a test
"""
        raw    = self._llm(prompt, max_tokens=2500, json_mode=True)
        result = safe_json(raw)
        return result if result else {"meta": {"objective": objective}, "error": "parse_failed"}

    # ── Main : accomplish ─────────────────────────────────────────
    def accomplish(self, objective: str,
                   output: str = "runtime.json") -> dict:
        from rich.console import Console
        from rich.panel   import Panel
        console = Console()

        # 1. Catalogue
        console.print("\n[cyan]① Chargement du catalogue...[/cyan]")
        catalogue = fetch_catalogue()
        console.print(f"   {len(catalogue)} packages disponibles")

        # 2. Sélection
        console.print("\n[cyan]② Sélection des packages par le LLM...[/cyan]")
        selected = self.select_packages(objective, catalogue)
        if not selected:
            console.print("[red]✗ Aucun package sélectionné[/red]")
            return {}
        console.print(f"\n   [bold]Stack sélectionnée :[/bold]")
        for pkg in selected:
            console.print(
                f"   • [green]{pkg['name']:25s}[/green] "
                f"[dim]{pkg.get('language','?'):12s}[/dim] "
                f"[yellow]{pkg.get('assigned_role','?'):15s}[/yellow] "
                f"{pkg.get('why','')[:60]}"
            )

        # 3. Extraction live
        console.print("\n[cyan]③ Extraction live des graphs...[/cyan]")
        graphs = self.extract_graphs(selected)
        if not graphs:
            console.print("[yellow]⚠ Aucun graph extrait — mode analyse sans graph[/yellow]")

        # 4. Analyse individuelle
        console.print("\n[cyan]④ Analyse de chaque couche...[/cyan]")
        analyses = {}
        for pkg in selected:
            name   = pkg["name"]
            role   = pkg.get("assigned_role", "?")
            graph  = graphs.get(name, {})
            console.print(f"   [{role.upper()}] {name}")
            analysis = self.analyze_graph(name, role, graph, objective)
            analyses[name] = analysis
            for line in analysis.split("\n"):
                if line.strip():
                    console.print(f"   [dim]{line.strip()}[/dim]")

        # 5. Runtime
        console.print("\n[cyan]⑤ Génération du runtime.json...[/cyan]")
        runtime = self.generate_runtime(objective, selected, graphs, analyses)

        # Sauvegarde
        Path(output).write_text(
            json.dumps(runtime, indent=2, ensure_ascii=False))

        # Affichage résumé
        modules = runtime.get("modules", {})
        edges   = runtime.get("edges", [])
        risks   = runtime.get("risks", [])
        console.print(Panel(
            f"[green]✓ runtime.json généré[/green]\n"
            f"  Modules  : {len(modules)}\n"
            f"  Edges    : {len(edges)}\n"
            f"  Risques  : {len(risks)}\n"
            f"  Fichier  : {output}",
            title=f"[bold cyan]GraphRuntime Goal — {objective[:50]}[/bold cyan]"
        ))

        return runtime
