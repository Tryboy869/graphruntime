"""
GraphRuntime CLI v1.1.0-beta
Universal architecture graph extractor, merger and runtime generator
"""
import click
import json
import os
import re
import sys
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import print as rprint

console = Console()

VERSION = "2.0.0-beta"
REGISTRY_BASE  = "https://raw.githubusercontent.com/tryboy869/graphruntime/main/registry"
REGISTRY_INDEX = f"{REGISTRY_BASE}/index.json"
CONFIG_PATH    = Path.home() / ".graphruntime" / "config.json"

# ── SKILL.md — auto-injection dans chaque appel LLM ─────────────
_SKILL_CACHE: dict = {"content": None}

def _load_skill() -> str:
    """Charge SKILL.md depuis GitHub (cache session)."""
    if _SKILL_CACHE["content"] is not None:
        return _SKILL_CACHE["content"]
    try:
        import urllib.request
        url = "https://raw.githubusercontent.com/tryboy869/graphruntime/main/SKILL.md"
        with urllib.request.urlopen(url, timeout=5) as resp:
            _SKILL_CACHE["content"] = resp.read().decode("utf-8")
    except Exception:
        _SKILL_CACHE["content"] = ""
    return _SKILL_CACHE["content"]

def _system_prompt() -> str:
    skill = _load_skill()
    base  = (
        "You are an expert software architect agent using GraphRuntime v2.0.\n"
        "You select packages from the catalogue, extract their architecture graphs live, "
        "analyze them, and generate production-ready runtime.json files.\n\n"
    )
    if skill:
        base += f"SKILL.md (read before any action):\n{skill}\n\n"
    base += (
        "CRITICAL RULES:\n"
        "- urllib3/requests/httpx = http_client ONLY — never cache\n"
        "- koin/dagger/hilt = dependency_injection ONLY — never monitoring\n"
        "- mocha/vitest/jest/rspec = testing ONLY — never production\n"
        "- Build realistic topologies: frontend→api→db (not everything→api)\n"
        "- entry_point must be a real source file, never a test file\n"
    )
    return base


LOCAL_REGISTRY = Path.home() / ".graphruntime" / "registry"

# ── Config ────────────────────────────────────────────────────────
def load_config() -> dict:
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text())
    return {
        "provider": os.environ.get("GRAPHRUNTIME_PROVIDER", "groq"),
        "model":    os.environ.get("GRAPHRUNTIME_MODEL", "llama-3.3-70b-versatile"),
        "api_key":  os.environ.get("GRAPHRUNTIME_API_KEY", ""),
    }

def save_config(cfg: dict):
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2))

# ── LLM Client ────────────────────────────────────────────────────
def get_llm_client(cfg: dict):
    provider = cfg.get("provider", "groq")
    api_key  = cfg.get("api_key", "")
    if not api_key:
        console.print("[red]✗ No API key configured.[/red]")
        console.print("Run: [bold]graphruntime config set api_key <your_key>[/bold]")
        sys.exit(1)
    if provider == "groq":
        from groq import Groq
        return Groq(api_key=api_key), cfg.get("model", "llama-3.3-70b-versatile")
    elif provider == "openai":
        from openai import OpenAI
        return OpenAI(api_key=api_key), cfg.get("model", "gpt-4o")
    elif provider == "anthropic":
        import anthropic
        return anthropic.Anthropic(api_key=api_key), cfg.get("model", "claude-sonnet-4-20250514")
    else:
        console.print(f"[red]Unknown provider: {provider}[/red]")
        sys.exit(1)

def call_llm(client, model: str, messages: list, max_tokens=2000, provider="groq") -> str:
    if provider == "anthropic":
        r = client.messages.create(model=model, max_tokens=max_tokens, messages=messages)
        return r.content[0].text.strip()
    else:
        r = client.chat.completions.create(
            model=model, messages=messages, max_tokens=max_tokens, temperature=0.2)
        return r.choices[0].message.content.strip()

# ── CLI Group ─────────────────────────────────────────────────────
@click.group()
@click.version_option(version=VERSION, prog_name="graphruntime")
def main():
    """
    GraphRuntime — Universal Architecture Graph CLI

    Extract, analyze, merge and execute software architectures
    across 42 languages using a universal graph.json format.

    Registry : https://github.com/tryboy869/graphruntime/tree/main/registry
    Docs     : https://github.com/tryboy869/graphruntime/blob/main/SKILL.md
    """
    pass

# ── EXTRACT ───────────────────────────────────────────────────────
@main.command()
@click.argument("source")
@click.option("--output",    "-o", default="graph.json", help="Output file path")
@click.option("--max-files",       default=500,          help="Maximum files to analyze")
def extract(source: str, output: str, max_files: int):
    """Extract the architecture graph from a project.

    \b
    SOURCE can be:
      ./local-path
      github:user/repo
      pip:package-name
      npm:package-name
      cargo:crate-name
    """
    from graphruntime.extractor import Extractor
    console.print(Panel(f"[bold cyan]Extracting graph from:[/bold cyan] {source}"))
    extractor = Extractor(max_files=max_files)
    with console.status("[bold green]Analyzing architecture..."):
        graph = extractor.extract(source)
    with open(output, "w", encoding="utf-8") as f:
        json.dump(graph, f, ensure_ascii=False, indent=2)
    stats = graph.get("stats", {})
    console.print(f"[green]✓ Graph saved to:[/green] {output}")
    console.print(f"  Nodes : {stats.get('fichiers_total', 0)}")
    console.print(f"  Edges : {stats.get('edges_total', 0)}")
    console.print(f"  Central nodes : {stats.get('noeuds_centraux', 0)}")

# ── PULL ──────────────────────────────────────────────────────────
@main.command()
@click.argument("package")
@click.option("--output", "-o", default=None, help="Output file (default: <package>_graph.json)")
def pull(package: str, output: str):
    """Pull a pre-analyzed graph from the GraphRuntime Registry.

    \b
    Examples:
      graphruntime pull flask
      graphruntime pull react
      graphruntime pull tokio
    """
    import requests
    output = output or f"{package.replace('/', '_')}_graph.json"
    with console.status(f"[bold green]Pulling {package} from registry..."):
        try:
            idx_r = requests.get(REGISTRY_INDEX, timeout=10)
            if idx_r.status_code == 200:
                index = idx_r.json()
                entry = next((e for e in index.get("packages", []) if e["name"] == package), None)
                if entry:
                    graph_url = f"{REGISTRY_BASE}/{entry['path'].lstrip('registry/')}"
                    r = requests.get(graph_url, timeout=10)
                    if r.status_code == 200:
                        with open(output, "w") as f:
                            f.write(r.text)
                        console.print(f"[green]✓ Graph saved to:[/green] {output}")
                        console.print(f"  Language : {entry.get('language','?')}")
                        console.print(f"  Nodes    : {entry.get('nodes','?')}")
                        console.print(f"  Edges    : {entry.get('edges','?')}")
                        return
            # Fallback: essaie tous les dossiers langues
            for lang in ["python","javascript","rust","go","java","cpp","csharp","ruby",
                         "php","swift","kotlin","scala","dart","elixir","haskell","shell",
                         "lua","clojure","nim","zig","infra","ai","r","custom"]:
                url = f"{REGISTRY_BASE}/{lang}/{package}.json"
                r = requests.get(url, timeout=5)
                if r.status_code == 200:
                    with open(output, "w") as f:
                        f.write(r.text)
                    console.print(f"[green]✓ Graph saved to:[/green] {output}")
                    return
            console.print(f"[yellow]⚠ '{package}' not in registry.[/yellow]")
            console.print(f"  Try: [bold]graphruntime extract pip:{package}[/bold]")
            console.print(f"  Or:  [bold]graphruntime add pip:{package}[/bold]")
        except Exception as e:
            console.print(f"[red]✗ Registry error: {e}[/red]")

# ── ADD ───────────────────────────────────────────────────────────
@main.command()
@click.argument("source")
@click.option("--name",     "-n", default=None,     help="Custom name (default: auto)")
@click.option("--language", "-l", default=None,     help="Language tag (default: auto)")
@click.option("--domain",   "-d", default="custom", help="Domain: backend/ai/infra/frontend/data/tools/custom")
@click.option("--output",   "-o", default=None,     help="Also save graph.json here")
@click.option("--registry", "-r", default=None,     help="Local registry dir (default: ~/.graphruntime/registry)")
@click.option("--no-index",       is_flag=True,     help="Don't update local index.json")
def add(source: str, name: str, language: str, domain: str,
        output: str, registry: str, no_index: bool):
    """Add any custom tool or project to your local registry.

    \b
    SOURCE accepts anything:
      ./my-project              local directory
      github:user/repo          GitHub repository
      pip:my-package            PyPI package
      npm:my-package            npm package
      cargo:my-crate            Rust crate
      https://github.com/u/r    direct URL (auto-resolved)

    \b
    Examples:
      graphruntime add ./my-api --name my-api --domain backend
      graphruntime add github:vercel/next.js --domain frontend
      graphruntime add pip:sqlalchemy --domain database
      graphruntime add https://github.com/redis/redis --language c
    """
    from graphruntime.extractor import Extractor

    # Résolution automatique de la source
    resolved = source
    if source.startswith("https://github.com/"):
        resolved = "github:" + source.replace("https://github.com/", "").rstrip("/")
        console.print(f"[dim]Resolved → {resolved}[/dim]")
    elif not any(source.startswith(p) for p in ["github:","pip:","npm:","cargo:","http"]):
        if Path(source).exists():
            resolved = str(Path(source).resolve())

    # Nom auto-détecté
    auto_name = name
    if not auto_name:
        for prefix in ["github:","pip:","npm:","cargo:"]:
            if resolved.startswith(prefix):
                auto_name = resolved[len(prefix):].split("/")[-1].rstrip(".git")
                break
        if not auto_name:
            auto_name = Path(resolved).name or "custom-project"

    console.print(Panel(
        f"[bold cyan]Adding to local registry[/bold cyan]\n"
        f"  Source   : {resolved}\n"
        f"  Name     : {auto_name}\n"
        f"  Domain   : {domain}",
        title="[cyan]graphruntime add[/cyan]"
    ))

    extractor = Extractor(max_files=500)
    with console.status(f"[bold green]Extracting graph from {resolved}..."):
        try:
            graph = extractor.extract(resolved)
        except Exception as e:
            console.print(f"[red]✗ Extraction failed: {e}[/red]")
            console.print("[yellow]Tips:[/yellow]")
            console.print("  • GitHub repos  : graphruntime add github:user/repo")
            console.print("  • Local paths   : graphruntime add ./my-project")
            console.print("  • PyPI packages : graphruntime add pip:package-name")
            raise SystemExit(1)

    stats = graph.get("stats", {})
    nodes = stats.get("fichiers_total", 0)
    edges = stats.get("edges_total",   0)

    if nodes < 1:
        console.print(f"[yellow]⚠ No nodes extracted from '{source}'.[/yellow]")
        raise SystemExit(1)

    # Langue auto-détectée
    detected_lang = language or (
        graph.get("meta", {}).get("langage", "") or
        graph.get("meta", {}).get("language", "") or "custom"
    ).lower().strip() or "custom"

    # Registry dir
    reg_dir  = Path(registry) if registry else LOCAL_REGISTRY
    reg_dir.mkdir(parents=True, exist_ok=True)
    lang_dir = reg_dir / detected_lang
    lang_dir.mkdir(exist_ok=True)

    safe_name  = re.sub(r"[^\w\-.]", "_", auto_name)
    graph_path = lang_dir / f"{safe_name}.json"

    graph.setdefault("meta", {}).update({
        "custom": True, "source": source,
        "domain": domain, "added_by": "graphruntime add",
    })
    graph_path.write_text(json.dumps(graph, ensure_ascii=False, indent=2))
    console.print(f"[green]✓ Graph saved:[/green] {graph_path}")

    if output:
        Path(output).write_text(json.dumps(graph, ensure_ascii=False, indent=2))
        console.print(f"[green]✓ Also saved to:[/green] {output}")

    if not no_index:
        idx_path = reg_dir / "index.json"
        index    = json.loads(idx_path.read_text()) if idx_path.exists() else {"packages": []}
        index["packages"] = [
            p for p in index.get("packages", [])
            if not (p.get("name") == auto_name and p.get("language") == detected_lang)
        ]
        index["packages"].append({
            "name": auto_name, "language": detected_lang, "domain": domain,
            "path": str(graph_path), "nodes": nodes, "edges": edges,
            "source": source, "custom": True,
        })
        index["packages"].sort(key=lambda x: (x.get("language",""), x.get("name","")))
        index["total"] = len(index["packages"])
        idx_path.write_text(json.dumps(index, ensure_ascii=False, indent=2))
        console.print(f"[green]✓ Index updated:[/green] {len(index['packages'])} entries")

    table = Table(title="Entry Added", show_header=False)
    table.add_column("Key",   style="cyan")
    table.add_column("Value", style="white")
    for k, v in [("Name", auto_name), ("Language", detected_lang), ("Domain", domain),
                 ("Nodes", str(nodes)), ("Edges", str(edges)), ("Saved", str(graph_path))]:
        table.add_row(k, v)
    console.print(table)
    console.print(f"\n[bold]Next:[/bold]")
    console.print(f"  graphruntime inspect {graph_path}")
    console.print(f"  graphruntime explain {graph_path}")

# ── LIST ──────────────────────────────────────────────────────────
@main.command("list")
@click.option("--registry", "-r", default=None,  help="Local registry dir")
@click.option("--language", "-l", default=None,  help="Filter by language")
@click.option("--domain",   "-d", default=None,  help="Filter by domain")
@click.option("--custom",         is_flag=True,  help="Only custom entries")
@click.option("--remote",         is_flag=True,  help="Show remote registry (GitHub, 331 packages)")
def list_cmd(registry: str, language: str, domain: str, custom: bool, remote: bool):
    """List all entries in the local or remote registry.

    \b
    Examples:
      graphruntime list
      graphruntime list --language python
      graphruntime list --domain ai
      graphruntime list --custom
      graphruntime list --remote
    """
    import requests

    if remote:
        with console.status("[bold green]Fetching remote registry..."):
            try:
                r = requests.get(REGISTRY_INDEX, timeout=10)
                r.raise_for_status()
                index = r.json()
            except Exception as e:
                console.print(f"[red]✗ Remote registry error: {e}[/red]")
                raise SystemExit(1)
        source_label = "Remote Registry (github.com/tryboy869/graphruntime)"
    else:
        reg_dir   = Path(registry) if registry else LOCAL_REGISTRY
        idx_path  = reg_dir / "index.json"
        if not idx_path.exists():
            console.print("[yellow]No local registry found.[/yellow]")
            console.print(f"  Expected : {idx_path}")
            console.print("  Run [bold]graphruntime add <source>[/bold] to add entries.")
            console.print("  Or  [bold]graphruntime list --remote[/bold] to see the public registry.")
            return
        index        = json.loads(idx_path.read_text())
        source_label = f"Local Registry ({reg_dir})"

    packages = index.get("packages", [])
    if language: packages = [p for p in packages if p.get("language","").lower() == language.lower()]
    if domain:   packages = [p for p in packages if p.get("domain","").lower()   == domain.lower()]
    if custom:   packages = [p for p in packages if p.get("custom", False)]

    if not packages:
        console.print("[yellow]No entries match your filters.[/yellow]")
        return

    table = Table(title=f"{source_label} — {len(packages)} entries", show_lines=False)
    table.add_column("Name",     style="cyan",    max_width=32)
    table.add_column("Language", style="yellow",  max_width=12)
    table.add_column("Domain",   style="magenta", max_width=12)
    table.add_column("Nodes",    justify="right", style="green")
    table.add_column("Edges",    justify="right", style="green")
    table.add_column("★",        justify="center")

    for p in packages:
        table.add_row(
            p.get("name","?"), p.get("language","?"), p.get("domain","custom"),
            str(p.get("nodes",0)), str(p.get("edges",0)),
            "[bold green]✓[/bold green]" if p.get("custom") else "",
        )
    console.print(table)
    langs   = len(set(p.get("language","") for p in packages))
    customs = sum(1 for p in packages if p.get("custom"))
    console.print(f"\n[dim]Total: {index.get('total', len(packages))} | Languages: {langs} | Custom: {customs}[/dim]")

# ── INSPECT ───────────────────────────────────────────────────────
@main.command()
@click.argument("graph_file")
@click.option("--nodes",    is_flag=True, help="Show all nodes")
@click.option("--patterns", is_flag=True, help="Show detected patterns")
def inspect(graph_file: str, nodes: bool, patterns: bool):
    """Show a human-readable summary of a graph.json."""
    graph = json.loads(Path(graph_file).read_text())
    meta  = graph.get("meta",  {})
    stats = graph.get("stats", {})
    console.print(Panel(
        f"[bold]{meta.get('projet', 'Unknown')}[/bold]\n"
        f"Language: {meta.get('langage','?')} | Schema: {meta.get('schema','?')}",
        title="[cyan]GraphRuntime Inspect[/cyan]"
    ))
    table = Table(title="Architecture Stats")
    table.add_column("Metric", style="cyan")
    table.add_column("Value",  style="green", justify="right")
    for k, v in stats.items():
        table.add_row(k.replace("_"," ").title(), str(v))
    console.print(table)
    if patterns or not nodes:
        pats = graph.get("patterns", [])
        if pats:
            console.print("\n[bold yellow]Detected Patterns:[/bold yellow]")
            for p in pats:
                console.print(f"  → {p}")
    if nodes:
        noeuds = graph.get("noeuds", {})
        nt = Table(title="Nodes")
        nt.add_column("File",  style="cyan")
        nt.add_column("Type",  style="yellow")
        nt.add_column("Lines", justify="right")
        nt.add_column("In",    justify="right")
        nt.add_column("Out",   justify="right")
        for k, v in sorted(noeuds.items(),
                           key=lambda x: len(x[1].get("est_appele_par",[])),
                           reverse=True)[:30]:
            nt.add_row(k, v.get("type_noeud","standard"),
                       str(v.get("lignes",0)),
                       str(len(v.get("est_appele_par",[]))),
                       str(len(v.get("appelle",[]))))
        console.print(nt)

# ── DIFF ──────────────────────────────────────────────────────────
@main.command()
@click.argument("graph_a")
@click.argument("graph_b")
def diff(graph_a: str, graph_b: str):
    """Show architectural differences between two graph.json files."""
    ga = json.loads(Path(graph_a).read_text())
    gb = json.loads(Path(graph_b).read_text())
    nodes_a = set(ga.get("noeuds", {}).keys())
    nodes_b = set(gb.get("noeuds", {}).keys())
    added   = nodes_b - nodes_a
    removed = nodes_a - nodes_b
    common  = nodes_a & nodes_b
    console.print(Panel("[bold cyan]Architectural Diff[/bold cyan]"))
    console.print(f"  [green]+{len(added)} nodes added[/green]")
    console.print(f"  [red]-{len(removed)} nodes removed[/red]")
    console.print(f"  [yellow]{len(common)} nodes in common[/yellow]")
    if added:
        console.print("\n[green]Added:[/green]")
        for n in sorted(added): console.print(f"  + {n}")
    if removed:
        console.print("\n[red]Removed:[/red]")
        for n in sorted(removed): console.print(f"  - {n}")
    edges_a   = set((e["de"],e["vers"]) for e in ga.get("edges",[]))
    edges_b   = set((e["de"],e["vers"]) for e in gb.get("edges",[]))
    console.print(f"\n  [green]+{len(edges_b-edges_a)} edges added[/green]")
    console.print(f"  [red]-{len(edges_a-edges_b)} edges removed[/red]")

# ── EXPLAIN ───────────────────────────────────────────────────────
@main.command()
@click.argument("graph_file")
def explain(graph_file: str):
    """Ask the LLM to explain the architecture from a graph.json."""
    cfg    = load_config()
    client, model = get_llm_client(cfg)
    graph  = json.loads(Path(graph_file).read_text())
    light  = {
        "meta": graph.get("meta",{}), "stats": graph.get("stats",{}),
        "patterns": graph.get("patterns",[]),
        "noeuds_cles": {
            k: {"sorties": v.get("sorties",[])[:4], "type_noeud": v.get("type_noeud"),
                "in": len(v.get("est_appele_par",[])), "out": len(v.get("appelle",[]))}
            for k, v in sorted(graph.get("noeuds",{}).items(),
                               key=lambda x: len(x[1].get("est_appele_par",[])),
                               reverse=True)[:15]
        }
    }
    prompt = (
        "You are a software architect expert.\n"
        "Analyze this graph.json and explain the architecture:\n\n"
        f"```json\n{json.dumps(light, indent=2)}\n```\n\n"
        "Provide:\n"
        "1. The main purpose of this project\n"
        "2. The 3 most critical nodes and why\n"
        "3. The architectural patterns detected\n"
        "4. Potential risks (circular deps, over-coupled nodes)\n"
        "5. How a developer should navigate this codebase\n\n"
        "Be concise and architectural."
    )
    with console.status("[bold green]LLM analyzing architecture..."):
        response = call_llm(client, model, [{"role":"user","content":prompt}],
                           max_tokens=1000, provider=cfg.get("provider","groq"))
    console.print(Panel(response, title="[cyan]Architecture Explanation[/cyan]"))

# ── MERGE ─────────────────────────────────────────────────────────
@main.command()
@click.argument("graph_a")
@click.argument("graph_b")
@click.option("--objective", "-obj", required=True, help="Fusion objective")
@click.option("--output",    "-o",   default="runtime.json", help="Output runtime file")
def merge(graph_a: str, graph_b: str, objective: str, output: str):
    """Merge two architecture graphs into a runtime.json."""
    from graphruntime.merger import Merger
    cfg    = load_config()
    client, model = get_llm_client(cfg)
    ga = json.loads(Path(graph_a).read_text())
    gb = json.loads(Path(graph_b).read_text())
    console.print(Panel(
        f"[bold]Merging:[/bold]\n"
        f"  A: {ga.get('meta',{}).get('projet','?')}\n"
        f"  B: {gb.get('meta',{}).get('projet','?')}\n"
        f"  Objective: {objective}",
        title="[cyan]GraphRuntime Merge[/cyan]"
    ))
    merger  = Merger(client, model, cfg.get("provider","groq"))
    runtime = merger.merge(ga, gb, objective)
    with open(output, "w", encoding="utf-8") as f:
        json.dump(runtime, f, ensure_ascii=False, indent=2)
    console.print(f"[green]✓ Runtime saved to:[/green] {output}")
    console.print(f"  Modules : {list(runtime.get('modules',{}).keys())}")
    console.print(f"  Edges   : {len(runtime.get('edges',[]))}")

# ── RUN ───────────────────────────────────────────────────────────
@main.command()
@click.argument("runtime_file")
@click.option("--input", "-i", "input_data", default=None, help="Input JSON data")
def run(runtime_file: str, input_data: str):
    """Execute a runtime.json pipeline."""
    from graphruntime.runner import Runner
    runtime = json.loads(Path(runtime_file).read_text())
    inp     = json.loads(input_data) if input_data else None
    console.print(Panel(
        f"[bold]Running:[/bold] {runtime.get('meta',{}).get('nom','?')}\n"
        f"Objective: {runtime.get('meta',{}).get('objectif','?')}",
        title="[cyan]GraphRuntime Run[/cyan]"
    ))
    runner = Runner(runtime)
    result = runner.execute(inp)
    console.print("\n[bold green]Result:[/bold green]")
    console.print(json.dumps(result, indent=2, ensure_ascii=False))

# ── MODIFY ────────────────────────────────────────────────────────
@main.command()
@click.argument("repo_path")
@click.option("--instruction", "-i", required=True, help="What to modify")
@click.option("--dry-run",           is_flag=True,  help="Show changes without applying")
def modify(repo_path: str, instruction: str, dry_run: bool):
    """Modify an existing repo guided by its graph."""
    from graphruntime.extractor import Extractor
    from graphruntime.modifier import Modifier
    cfg    = load_config()
    client, model = get_llm_client(cfg)
    console.print(Panel(f"[bold]Modifying:[/bold] {repo_path}\n[bold]Instruction:[/bold] {instruction}"))
    extractor = Extractor()
    with console.status("Extracting graph..."):
        graph = extractor.extract(repo_path)
    modifier = Modifier(client, model, cfg.get("provider","groq"))
    changes  = modifier.plan_changes(graph, instruction)
    console.print("\n[bold yellow]Planned changes:[/bold yellow]")
    for c in changes:
        console.print(f"  → {c['fichier']} : {c['action']}")
    if not dry_run:
        if click.confirm("Apply these changes?"):
            modifier.apply_changes(repo_path, changes, graph)
            console.print("[green]✓ Changes applied[/green]")

# ── CREATE ────────────────────────────────────────────────────────
@main.command()
@click.argument("repo_path")
@click.option("--missing", "-m", required=True, help="Description of missing file")
def create(repo_path: str, missing: str):
    """Create a missing file and connect it to the existing graph."""
    from graphruntime.extractor import Extractor
    from graphruntime.creator import Creator
    cfg    = load_config()
    client, model = get_llm_client(cfg)
    extractor = Extractor()
    with console.status("Extracting graph..."):
        graph = extractor.extract(repo_path)
    creator = Creator(client, model, cfg.get("provider","groq"))
    result  = creator.create_file(graph, repo_path, missing)
    console.print(f"[green]✓ Created:[/green] {result['path']}")
    console.print(f"  Edges added: {result.get('edges_added',[])}")

# ── REWIRE ────────────────────────────────────────────────────────
@main.command()
@click.argument("repo_path")
@click.option("--from-edge", "from_edge", required=True, help="Edge to change")
@click.option("--to-edge",   "to_edge",   required=True, help="New edge")
def rewire(repo_path: str, from_edge: str, to_edge: str):
    """Invert or reroute a data flow between modules."""
    from graphruntime.extractor import Extractor
    from graphruntime.rewirer import Rewirer
    cfg    = load_config()
    client, model = get_llm_client(cfg)
    extractor = Extractor()
    graph     = extractor.extract(repo_path)
    rewirer   = Rewirer(client, model, cfg.get("provider","groq"))
    result    = rewirer.rewire(graph, repo_path, from_edge, to_edge)
    console.print(f"[green]✓ Rewired:[/green] {from_edge} → {to_edge}")
    console.print(f"  Files modified: {result.get('files_modified',[])}")

# ── WATCH ─────────────────────────────────────────────────────────
@main.command()
@click.argument("repo_path")
@click.option("--llm", is_flag=True, help="Enable LLM alerts for architectural issues")
def watch(repo_path: str, llm: bool):
    """Watch a repo and rebuild graph on file changes."""
    import time
    from graphruntime.extractor import Extractor
    extractor   = Extractor()
    last_mtimes = {}
    console.print(f"[bold cyan]Watching:[/bold cyan] {repo_path}")
    console.print("Press Ctrl+C to stop\n")
    try:
        while True:
            changed = []
            for root, _, files in os.walk(repo_path):
                for f in files:
                    path  = os.path.join(root, f)
                    mtime = os.path.getmtime(path)
                    if path not in last_mtimes or last_mtimes[path] != mtime:
                        last_mtimes[path] = mtime
                        changed.append(path)
            if changed:
                console.print(f"[yellow]Changes detected:[/yellow] {len(changed)} files")
                with console.status("Rebuilding graph..."):
                    graph = extractor.extract(repo_path)
                circs = [e for e in graph.get("edges",[]) if e["type"] == "circulaire"]
                if circs:
                    console.print(f"[red]⚠ {len(circs)} circular dependencies[/red]")
                console.print(f"[green]✓ Rebuilt:[/green] {graph['stats']['fichiers_total']} nodes")
            time.sleep(2)
    except KeyboardInterrupt:
        console.print("\n[bold]Watch stopped[/bold]")

# ── VALIDATE ──────────────────────────────────────────────────────
@main.command()
@click.argument("repo_path")
@click.option("--before", default=None, help="Graph before changes")
def validate(repo_path: str, before: str):
    """Validate the architectural integrity of a repo."""
    from graphruntime.extractor import Extractor
    extractor = Extractor()
    with console.status("Extracting current graph..."):
        graph = extractor.extract(repo_path)
    issues, success = [], []
    circs  = [e for e in graph.get("edges",[]) if e["type"] == "circulaire"]
    if circs: issues.append(f"{len(circs)} circular dependencies")
    else:     success.append("No circular dependencies")
    noeuds = graph.get("noeuds",{})
    total  = len(noeuds)
    hubs   = [k for k, v in noeuds.items() if len(v.get("est_appele_par",[])) > total * 0.3]
    if hubs: issues.append(f"Over-coupled nodes: {hubs}")
    else:    success.append("No over-coupled nodes")
    if before and Path(before).exists():
        gb      = json.loads(Path(before).read_text())
        removed = set(gb.get("noeuds",{}).keys()) - set(noeuds.keys())
        if removed: issues.append(f"Removed public nodes: {removed}")
    console.print(Panel(
        "\n".join([f"[green]✓ {s}[/green]" for s in success] +
                  [f"[red]✗ {i}[/red]"   for i in issues]),
        title="[cyan]Validation Results[/cyan]"
    ))
    if issues: sys.exit(1)

# ── GOAL ──────────────────────────────────────────────────────────
@main.command()
@click.argument("objective")
@click.option("--output", "-o", default="runtime.json")
def goal(objective: str, output: str):
    """Let the AI choose, extract, merge and run everything from an objective."""
    from graphruntime.agent import GoalAgent
    cfg    = load_config()
    client, model = get_llm_client(cfg)
    console.print(Panel(f"[bold cyan]Goal:[/bold cyan] {objective}"))
    agent  = GoalAgent(client, model, cfg.get("provider","groq"))
    result = agent.accomplish(objective, output)
    console.print(f"\n[green]✓ Runtime generated:[/green] {output}")
    console.print(f"  Packages used: {result.get('packages',[])}")

# ── PUBLISH ───────────────────────────────────────────────────────
@main.command()
@click.argument("graph_file")
@click.option("--package",  required=True)
@click.option("--version",  required=True)
@click.option("--language", required=True,
              type=click.Choice(["python","javascript","rust","go","java","cpp","csharp",
                                 "ruby","php","swift","kotlin","scala","dart","elixir",
                                 "haskell","shell","lua","clojure","nim","zig","infra","ai","r","custom"]))
def publish(graph_file: str, package: str, version: str, language: str):
    """Contribute a graph.json to the GraphRuntime Registry via GitHub PR."""
    console.print(Panel(
        f"Publishing [bold]{package}@{version}[/bold] ({language}) to registry",
        title="[cyan]GraphRuntime Publish[/cyan]"
    ))
    console.print(f"  File   : {graph_file}")
    console.print(f"  Target : registry/{language}/{package}@{version}.json")
    console.print("\n[yellow]→ Fork the repo and submit a PR:[/yellow]")
    console.print("  https://github.com/tryboy869/graphruntime/tree/main/registry")

# ── CONFIG ────────────────────────────────────────────────────────
@main.group()
def config():
    """Manage GraphRuntime configuration."""
    pass

@config.command("set")
@click.argument("key")
@click.argument("value")
def config_set(key: str, value: str):
    """Set a configuration value."""
    cfg = load_config()
    cfg[key] = value
    save_config(cfg)
    console.print(f"[green]✓ Set {key} = {'***' if 'key' in key.lower() else value}[/green]")

@config.command("show")
def config_show():
    """Show current configuration."""
    cfg = load_config()
    for k, v in cfg.items():
        console.print(f"  {k}: {'***' if 'key' in k.lower() and v else v}")

if __name__ == "__main__":
    main()
