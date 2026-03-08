"""GraphRuntime — Modifier, Creator, Rewirer, Agent modules"""
import json, os, re, requests
from pathlib import Path


def _call_llm(client, model, provider, messages, max_tokens=2000):
    if provider == "anthropic":
        r = client.messages.create(model=model, max_tokens=max_tokens, messages=messages)
        return r.content[0].text.strip()
    else:
        r = client.chat.completions.create(
            model=model, messages=messages,
            max_tokens=max_tokens, temperature=0.2)
        return r.choices[0].message.content.strip()


def _extract_json(text):
    m = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
    if m:
        try: return json.loads(m.group(1))
        except: pass
    m2 = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
    if m2:
        try: return json.loads(m2.group(0))
        except: pass
    return None


# ── Modifier ──────────────────────────────────────────────────────
class Modifier:
    def __init__(self, client, model, provider):
        self.client   = client
        self.model    = model
        self.provider = provider

    def plan_changes(self, graph: dict, instruction: str) -> list:
        graph_light = {
            "patterns": graph.get("patterns", []),
            "noeuds_cles": {
                k: {"sorties": v.get("sorties", [])[:4], "type_noeud": v.get("type_noeud")}
                for k, v in sorted(
                    graph.get("noeuds", {}).items(),
                    key=lambda x: len(x[1].get("est_appele_par", [])), reverse=True
                )[:10]
            }
        }
        prompt = (
            f"Graph:\n```json\n{json.dumps(graph_light, indent=2)}\n```\n\n"
            f"Instruction: {instruction}\n\n"
            f"Which files need to change? JSON only:\n"
            f'[{{"fichier":"...","action":"modify|create|delete","raison":"..."}}]'
        )
        resp = _call_llm(self.client, self.model, self.provider,
                         [{"role": "user", "content": prompt}], 800)
        return _extract_json(resp) or []

    def apply_changes(self, repo_path: str, changes: list, graph: dict):
        for change in changes:
            fichier = change.get("fichier", "")
            action  = change.get("action", "modify")
            path    = Path(repo_path) / fichier

            if action == "modify" and path.exists():
                original = path.read_text(encoding="utf-8", errors="ignore")
                noeud    = graph.get("noeuds", {}).get(fichier, {})
                prompt   = (
                    f"File: {fichier}\n"
                    f"Context: {json.dumps(noeud, indent=2)[:500]}\n\n"
                    f"Original code:\n```\n{original[:3000]}\n```\n\n"
                    f"Action: {change.get('raison','')}\n\n"
                    f"Return ONLY the complete modified code. No markdown."
                )
                new_code = _call_llm(self.client, self.model, self.provider,
                                     [{"role": "user", "content": prompt}], 2000)
                new_code = re.sub(r"^```\w*\s*", "", new_code)
                new_code = re.sub(r"\s*```$", "", new_code).strip()
                path.write_text(new_code, encoding="utf-8")


# ── Creator ───────────────────────────────────────────────────────
class Creator:
    def __init__(self, client, model, provider):
        self.client   = client
        self.model    = model
        self.provider = provider

    def create_file(self, graph: dict, repo_path: str, description: str) -> dict:
        graph_light = {
            "patterns": graph.get("patterns", []),
            "noeuds": {k: {"sorties": v.get("sorties", [])[:3]}
                       for k, v in list(graph.get("noeuds", {}).items())[:8]}
        }
        prompt = (
            f"Project graph:\n```json\n{json.dumps(graph_light, indent=2)}\n```\n\n"
            f"Create a new file: {description}\n\n"
            f"Return JSON:\n"
            f'{{"path":"relative/path.py","code":"...","edges_added":["other_file.py"]}}\n'
            f"JSON only."
        )
        resp   = _call_llm(self.client, self.model, self.provider,
                           [{"role": "user", "content": prompt}], 2000)
        result = _extract_json(resp) or {"path": "new_file.py", "code": "# TODO", "edges_added": []}

        path = Path(repo_path) / result["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(result.get("code", ""), encoding="utf-8")
        return result


# ── Rewirer ───────────────────────────────────────────────────────
class Rewirer:
    def __init__(self, client, model, provider):
        self.client   = client
        self.model    = model
        self.provider = provider

    def rewire(self, graph: dict, repo_path: str,
               from_edge: str, to_edge: str) -> dict:
        prompt = (
            f"Project has these patterns: {graph.get('patterns', [])[:5]}\n\n"
            f"Current edge: {from_edge}\n"
            f"Desired edge: {to_edge}\n\n"
            f"What files need to change to rewire this dependency?\n"
            f'JSON: {{"files_modified":["..."],"changes":[{{"file":"...","change":"..."}}]}}'
        )
        resp   = _call_llm(self.client, self.model, self.provider,
                           [{"role": "user", "content": prompt}], 800)
        return _extract_json(resp) or {"files_modified": [], "changes": []}


# ── GoalAgent ─────────────────────────────────────────────────────
REGISTRY_BASE = "https://raw.githubusercontent.com/tryboy869/graphruntime/main/registry"

class GoalAgent:
    def __init__(self, client, model, provider):
        self.client   = client
        self.model    = model
        self.provider = provider

    def accomplish(self, objective: str, output: str) -> dict:
        from graphruntime.extractor import Extractor
        from graphruntime.merger    import Merger

        # Step 1: Identify needed packages
        prompt = (
            f"Objective: {objective}\n\n"
            f"Which 2-3 existing packages best accomplish this?\n"
            f'JSON only: {{"packages":[{{"name":"...","registry":"pip|npm|cargo|github","reason":"..."}}]}}'
        )
        resp = _call_llm(self.client, self.model, self.provider,
                         [{"role": "user", "content": prompt}], 600)
        plan = _extract_json(resp) or {"packages": []}

        packages = plan.get("packages", [])[:3]
        graphs   = []
        names    = []

        extractor = Extractor(max_files=200)

        for pkg in packages:
            name     = pkg.get("name", "")
            registry = pkg.get("registry", "pip")
            names.append(name)

            # Try registry first
            try:
                r = requests.get(f"{REGISTRY_BASE}/index.json", timeout=5)
                if r.status_code == 200:
                    idx   = r.json()
                    entry = next((e for e in idx.get("packages", [])
                                  if e["name"] == name), None)
                    if entry:
                        gr = requests.get(f"{REGISTRY_BASE}/{entry['path']}", timeout=5)
                        if gr.status_code == 200:
                            graphs.append(gr.json())
                            continue
            except:
                pass

            # Extract directly
            try:
                source = f"{registry}:{name}"
                graphs.append(extractor.extract(source))
            except Exception as e:
                print(f"Warning: Could not extract {name}: {e}")

        if len(graphs) < 2:
            return {"packages": names, "error": "Could not extract enough graphs"}

        # Merge all graphs
        merger  = Merger(self.client, self.model, self.provider)
        runtime = merger.merge(graphs[0], graphs[1], objective)

        # Add more if available
        for g in graphs[2:]:
            runtime = merger.merge(
                {"meta": {"projet": "current_runtime"}, "noeuds": {}, "edges": []},
                g, objective
            )

        with open(output, "w", encoding="utf-8") as f:
            json.dump(runtime, f, indent=2, ensure_ascii=False)

        return {"packages": names, "runtime": output}
