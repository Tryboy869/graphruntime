"""
GraphRuntime CLI
Universal architecture graph extractor, merger and runtime generator
"""
import click
import json
import os
import sys
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import print as rprint

console = Console()

REGISTRY_BASE = "https://raw.githubusercontent.com/tryboy869/graphruntime/main/registry"
CONFIG_PATH   = Path.home() / ".graphruntime" / "config.json"

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
        r = client.messages.create(
            model=model, max_tokens=max_tokens,
            messages=messages
        )
        return r.content[0].text.strip()
    else:
        r = client.chat.completions.create(
            model=model, messages=messages,
            max_tokens=max_tokens, temperature=0.2
        )
        return r.choices[0].message.content.strip()

# ── CLI Group ─────────────────────────────────────────────────────
@click.group()
@click.version_option(version="1.0.0-beta", prog_name="graphruntime")
def main():
    """
    GraphRuntime — Universal Architecture Graph CLI

    Extract, analyze, merge and execute software architectures
    across 42 languages using a universal graph.json format.

    Docs: https://github.com/tryboy869/graphruntime/blob/main/SKILL.md
    """
    pass

# ── EXTRACT ───────────────────────────────────────────────────────
@main.command()
@click.argument("source")
@click.option("--output", "-o", default="graph.json", help="Output file path")
@click.option("--max-files", default=500, help="Maximum files to analyze")
def extract(source: str, output: str, max_files: int):
    """Extract the architecture graph from a project.

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
    """Pull a pre-analyzed graph from the GraphRuntime Registry."""
    import requests

    output = output or f"{package.replace('/', '_')}_graph.json"

    # Try to find in index first
    index_url = f"{REGISTRY_BASE}/index.json"
    with console.status(f"[bold green]Pulling {package} from registry..."):
        try:
            idx_r = requests.get(index_url, timeout=10)
            if idx_r.status_code == 200:
                index = idx_r.json()
                entry = next((e for e in index.get("packages", [])
                              if e["name"] == package), None)
                if entry:
                    graph_url = f"{REGISTRY_BASE}/{entry['path']}"
                    r = requests.get(graph_url, timeout=10)
                    if r.status_code == 200:
                        with open(output, "w") as f:
                            f.write(r.text)
                        console.print(f"[green]✓ Graph saved to:[/green] {output}")
                        return

            # Fallback: try direct path
            for lang in ["python", "javascript", "rust", "go", "infra", "ai"]:
                url = f"{REGISTRY_BASE}/{lang}/{package}.json"
                r = requests.get(url, timeout=5)
                if r.status_code == 200:
                    with open(output, "w") as f:
                        f.write(r.text)
                    console.print(f"[green]✓ Graph saved to:[/green] {output}")
                    return

            console.print(f"[yellow]⚠ '{package}' not in registry.[/yellow]")
            console.print(f"Try: [bold]graphruntime extract pip:{package}[/bold]")

        except Exception as e:
            console.print(f"[red]✗ Registry error: {e}[/red]")

# ── INSPECT ───────────────────────────────────────────────────────
@main.command()
@click.argument("graph_file")
@click.option("--nodes", is_flag=True, help="Show all nodes")
@click.option("--patterns", is_flag=True, help="Show detected patterns")
def inspect(graph_file: str, nodes: bool, patterns: bool):
    """Show a human-readable summary of a graph.json."""
    graph = json.loads(Path(graph_file).read_text())
    meta  = graph.get("meta", {})
    stats = graph.get("stats", {})

    console.print(Panel(
        f"[bold]{meta.get('projet', 'Unknown')}[/bold]\n"
        f"Language: {meta.get('langage', '?')} | "
        f"Schema: {meta.get('schema', '?')}",
        title="[cyan]GraphRuntime Inspect[/cyan]"
    ))

    table = Table(title="Architecture Stats")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green", justify="right")
    for k, v in stats.items():
        table.add_row(k.replace("_", " ").title(), str(v))
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
        nt.add_column("File", style="cyan")
        nt.add_column("Type", style="yellow")
        nt.add_column("Lines", justify="right")
        nt.add_column("In", justify="right")
        nt.add_column("Out", justify="right")
        for k, v in sorted(noeuds.items(),
                            key=lambda x: len(x[1].get("est_appele_par", [])),
                            reverse=True)[:30]:
            nt.add_row(
                k, v.get("type_noeud", "standard"),
                str(v.get("lignes", 0)),
                str(len(v.get("est_appele_par", []))),
                str(len(v.get("appelle", [])))
            )
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

    # Edge diff
    edges_a = set((e["de"], e["vers"]) for e in ga.get("edges", []))
    edges_b = set((e["de"], e["vers"]) for e in gb.get("edges", []))
    new_edges  = edges_b - edges_a
    lost_edges = edges_a - edges_b

    console.print(f"\n  [green]+{len(new_edges)} edges added[/green]")
    console.print(f"  [red]-{len(lost_edges)} edges removed[/red]")

# ── EXPLAIN ───────────────────────────────────────────────────────
@main.command()
@click.argument("graph_file")
def explain(graph_file: str):
    """Ask the LLM to explain the architecture from a graph.json."""
    cfg    = load_config()
    client, model = get_llm_client(cfg)

    graph  = json.loads(Path(graph_file).read_text())

    # Lightweight version for LLM
    graph_light = {
        "meta":     graph.get("meta", {}),
        "stats":    graph.get("stats", {}),
        "patterns": graph.get("patterns", []),
        "noeuds_cles": {
            k: {
                "sorties": v.get("sorties", [])[:4],
                "type_noeud": v.get("type_noeud"),
                "est_appele_par_count": len(v.get("est_appele_par", [])),
                "appelle_count": len(v.get("appelle", [])),
            }
            for k, v in sorted(
                graph.get("noeuds", {}).items(),
                key=lambda x: len(x[1].get("est_appele_par", [])),
                reverse=True
            )[:15]
        }
    }

    prompt = (
        f"You are a software architect expert.\n"
        f"Analyze this graph.json and explain the architecture:\n\n"
        f"```json\n{json.dumps(graph_light, indent=2)}\n```\n\n"
        f"Provide:\n"
        f"1. The main purpose of this project\n"
        f"2. The 3 most critical nodes and why\n"
        f"3. The architectural patterns detected\n"
        f"4. Potential risks (circular deps, over-coupled nodes)\n"
        f"5. How a developer should navigate this codebase\n\n"
        f"Be concise and architectural."
    )

    with console.status("[bold green]LLM analyzing architecture..."):
        response = call_llm(
            client, model,
            [{"role": "user", "content": prompt}],
            max_tokens=1000,
            provider=cfg.get("provider", "groq")
        )

    console.print(Panel(response, title="[cyan]Architecture Explanation[/cyan]"))

# ── MERGE ─────────────────────────────────────────────────────────
@main.command()
@click.argument("graph_a")
@click.argument("graph_b")
@click.option("--objective", "-obj", required=True, help="Fusion objective")
@click.option("--output", "-o", default="runtime.json", help="Output runtime file")
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

    merger  = Merger(client, model, cfg.get("provider", "groq"))
    runtime = merger.merge(ga, gb, objective)

    with open(output, "w", encoding="utf-8") as f:
        json.dump(runtime, f, ensure_ascii=False, indent=2)

    console.print(f"[green]✓ Runtime saved to:[/green] {output}")
    modules = list(runtime.get("modules", {}).keys())
    edges   = runtime.get("edges", [])
    console.print(f"  Modules : {modules}")
    console.print(f"  Edges   : {len(edges)}")

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
@click.option("--dry-run", is_flag=True, help="Show changes without applying")
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

    modifier = Modifier(client, model, cfg.get("provider", "groq"))
    changes  = modifier.plan_changes(graph, instruction)

    console.print(f"\n[bold yellow]Planned changes:[/bold yellow]")
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

    creator = Creator(client, model, cfg.get("provider", "groq"))
    result  = creator.create_file(graph, repo_path, missing)

    console.print(f"[green]✓ Created:[/green] {result['path']}")
    console.print(f"  Edges added: {result.get('edges_added', [])}")

# ── REWIRE ────────────────────────────────────────────────────────
@main.command()
@click.argument("repo_path")
@click.option("--from-edge", "from_edge", required=True, help="Edge to change (e.g. 'a→b')")
@click.option("--to-edge",   "to_edge",   required=True, help="New edge (e.g. 'b→a')")
def rewire(repo_path: str, from_edge: str, to_edge: str):
    """Invert or reroute a data flow between modules."""
    from graphruntime.extractor import Extractor
    from graphruntime.rewirer import Rewirer

    cfg    = load_config()
    client, model = get_llm_client(cfg)

    extractor = Extractor()
    graph     = extractor.extract(repo_path)

    rewirer = Rewirer(client, model, cfg.get("provider", "groq"))
    result  = rewirer.rewire(graph, repo_path, from_edge, to_edge)

    console.print(f"[green]✓ Rewired:[/green] {from_edge} → {to_edge}")
    console.print(f"  Files modified: {result.get('files_modified', [])}")

# ── WATCH ─────────────────────────────────────────────────────────
@main.command()
@click.argument("repo_path")
@click.option("--llm", is_flag=True, help="Enable LLM alerts for architectural issues")
def watch(repo_path: str, llm: bool):
    """Watch a repo and rebuild graph on file changes."""
    import time
    from graphruntime.extractor import Extractor

    extractor = Extractor()
    console.print(f"[bold cyan]Watching:[/bold cyan] {repo_path}")
    console.print("Press Ctrl+C to stop\n")

    last_mtimes = {}

    try:
        while True:
            changed = []
            for root, _, files in os.walk(repo_path):
                for f in files:
                    path = os.path.join(root, f)
                    mtime = os.path.getmtime(path)
                    if path not in last_mtimes or last_mtimes[path] != mtime:
                        last_mtimes[path] = mtime
                        changed.append(path)

            if changed:
                console.print(f"[yellow]Changes detected:[/yellow] {len(changed)} files")
                with console.status("Rebuilding graph..."):
                    graph = extractor.extract(repo_path)

                # Check for new circular deps
                circulaires = [e for e in graph.get("edges", []) if e["type"] == "circulaire"]
                if circulaires:
                    console.print(f"[red]⚠ {len(circulaires)} circular dependencies detected[/red]")

                console.print(f"[green]✓ Graph rebuilt:[/green] {graph['stats']['fichiers_total']} nodes, {graph['stats']['edges_total']} edges")

            time.sleep(2)
    except KeyboardInterrupt:
        console.print("\n[bold]Watch stopped[/bold]")

# ── VALIDATE ──────────────────────────────────────────────────────
@main.command()
@click.argument("repo_path")
@click.option("--before", default=None, help="Graph before changes (for comparison)")
def validate(repo_path: str, before: str):
    """Validate the architectural integrity of a repo."""
    from graphruntime.extractor import Extractor

    extractor = Extractor()
    with console.status("Extracting current graph..."):
        graph = extractor.extract(repo_path)

    issues  = []
    success = []

    # Check circular deps
    circulaires = [e for e in graph.get("edges", []) if e["type"] == "circulaire"]
    if circulaires:
        issues.append(f"{len(circulaires)} circular dependencies")
    else:
        success.append("No circular dependencies")

    # Check super-hubs
    noeuds = graph.get("noeuds", {})
    total  = len(noeuds)
    hubs   = [k for k, v in noeuds.items() if len(v.get("est_appele_par", [])) > total * 0.3]
    if hubs:
        issues.append(f"Over-coupled nodes: {hubs}")
    else:
        success.append("No over-coupled nodes")

    # Compare with before
    if before and Path(before).exists():
        gb       = json.loads(Path(before).read_text())
        nodes_b  = set(gb.get("noeuds", {}).keys())
        nodes_a  = set(noeuds.keys())
        removed  = nodes_b - nodes_a
        if removed:
            issues.append(f"Removed public nodes: {removed}")

    console.print(Panel(
        "\n".join([f"[green]✓ {s}[/green]" for s in success] +
                  [f"[red]✗ {i}[/red]" for i in issues]),
        title="[cyan]Validation Results[/cyan]"
    ))

    if issues:
        sys.exit(1)

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

    agent  = GoalAgent(client, model, cfg.get("provider", "groq"))
    result = agent.accomplish(objective, output)

    console.print(f"\n[green]✓ Runtime generated:[/green] {output}")
    console.print(f"  Packages used: {result.get('packages', [])}")

# ── PUBLISH ───────────────────────────────────────────────────────
@main.command()
@click.argument("graph_file")
@click.option("--package", required=True, help="Package name")
@click.option("--version", required=True, help="Package version")
@click.option("--language", required=True,
              type=click.Choice(["python","javascript","rust","go","infra","ai"]))
def publish(graph_file: str, package: str, version: str, language: str):
    """Contribute a graph.json to the GraphRuntime Registry via GitHub PR."""
    import subprocess

    console.print(Panel(
        f"Publishing [bold]{package}@{version}[/bold] ({language}) to registry",
        title="[cyan]GraphRuntime Publish[/cyan]"
    ))
    console.print("This will open a GitHub PR to the registry.")
    console.print(f"  File: {graph_file}")
    console.print(f"  Target: registry/{language}/{package}@{version}.json")
    console.print("\n[yellow]Manual step: Fork the repo and submit a PR with this file.[/yellow]")
    console.print("Registry: https://github.com/tryboy869/graphruntime/tree/main/registry")

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
    console.print(f"[green]✓ Set {key} = {value}[/green]")

@config.command("show")
def config_show():
    """Show current configuration."""
    cfg = load_config()
    for k, v in cfg.items():
        val = "***" if "key" in k.lower() and v else v
        console.print(f"  {k}: {val}")

if __name__ == "__main__":
    main()
