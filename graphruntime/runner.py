"""GraphRuntime — Runner module"""
import json, subprocess, sys, os


class Runner:
    def __init__(self, runtime: dict):
        self.runtime = runtime

    def _resolve_order(self) -> list:
        modules = self.runtime.get("modules", {})
        edges   = self.runtime.get("edges", [])
        entree  = self.runtime.get("entree")

        if entree:
            order   = [entree]
            visited = {entree}
            while True:
                nexts = [e["vers"] for e in edges
                         if e["de"] in visited and e["vers"] not in visited]
                if not nexts: break
                order.extend(nexts)
                visited.update(nexts)
            return order

        # Topological sort fallback
        targets = set(e["vers"] for e in edges)
        sources = set(e["de"]   for e in edges)
        starts  = (sources - targets) or set(modules.keys())
        order   = list(starts)
        visited = set(order)
        while True:
            nexts = [e["vers"] for e in edges
                     if e["de"] in visited and e["vers"] not in visited]
            if not nexts: break
            order.extend(nexts)
            visited.update(nexts)
        return order

    def execute(self, input_data=None) -> dict:
        modules = self.runtime.get("modules", {})
        order   = self._resolve_order()

        buffer = json.dumps(input_data) if input_data else "{}"

        for nom in order:
            mod  = modules.get(nom)
            if not mod:
                continue
            code = mod.get("code")
            if not code:
                continue

            lang = mod.get("langage", "python")
            if lang == "python":
                cmd = [sys.executable, "-c", code]
            elif lang in ("javascript", "typescript", "node"):
                cmd = ["node", "-e", code]
            else:
                continue

            result = subprocess.run(
                cmd, input=buffer,
                capture_output=True, text=True, timeout=30,
                env={**os.environ, "NODE_PATH": "/home/claude/.npm-global/lib/node_modules"}
            )

            if result.returncode != 0:
                return {"error": f"Module '{nom}' failed: {result.stderr[:200]}"}

            buffer = result.stdout.strip()

        try:
            return json.loads(buffer)
        except:
            return {"output": buffer}
