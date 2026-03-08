"""GraphRuntime — Merger module"""
import json, re


def _graph_light(graph: dict, max_nodes: int = 12) -> dict:
    noeuds = sorted(
        graph.get("noeuds", {}).items(),
        key=lambda x: len(x[1].get("est_appele_par", [])),
        reverse=True
    )[:max_nodes]
    return {
        "meta":     graph.get("meta", {}),
        "stats":    graph.get("stats", {}),
        "patterns": graph.get("patterns", [])[:8],
        "noeuds_cles": {
            k: {
                "sorties":           v.get("sorties", [])[:5],
                "appelle":           v.get("appelle", [])[:4],
                "est_appele_par":    v.get("est_appele_par", [])[:4],
                "type_noeud":        v.get("type_noeud"),
            }
            for k, v in noeuds
        }
    }


def _extract_json(text: str) -> dict | None:
    m = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
    if m:
        try: return json.loads(m.group(1))
        except: pass
    m2 = re.search(r"(\{.*\})", text, re.DOTALL)
    if m2:
        try: return json.loads(m2.group(0))
        except: pass
    return None


class Merger:
    def __init__(self, client, model: str, provider: str):
        self.client   = client
        self.model    = model
        self.provider = provider

    def _call(self, messages, max_tokens=2000):
        if self.provider == "anthropic":
            r = self.client.messages.create(
                model=self.model, max_tokens=max_tokens, messages=messages)
            return r.content[0].text.strip()
        else:
            r = self.client.chat.completions.create(
                model=self.model, messages=messages,
                max_tokens=max_tokens, temperature=0.1)
            return r.choices[0].message.content.strip()

    def merge(self, graph_a: dict, graph_b: dict, objective: str) -> dict:
        ga = _graph_light(graph_a)
        gb = _graph_light(graph_b)

        # Step 1: Analyze A
        resp_a = self._call([{"role": "user", "content":
            f"Analyze this architecture graph:\n```json\n{json.dumps(ga, indent=2)}\n```\n"
            f"In 3 sentences: main purpose, key nodes, public interface."}], 400)

        # Step 2: Analyze B
        resp_b = self._call([{"role": "user", "content":
            f"Analyze this architecture graph:\n```json\n{json.dumps(gb, indent=2)}\n```\n"
            f"In 3 sentences: main purpose, key nodes, public interface."}], 400)

        # Step 3: Generate runtime
        prompt = (
            f"You analyzed two systems:\n\nA: {resp_a}\n\nB: {resp_b}\n\n"
            f"Objective: {objective}\n\n"
            f"Generate a runtime.json that merges them. Format:\n"
            f'{{"meta":{{"nom":"...","objectif":"...","langages":[]}},'
            f'"modules":{{"name":{{"langage":"...","role":"...","entree_format":{{}},"sortie_format":{{}}}}}},'
            f'"edges":[{{"de":"...","vers":"...","format":{{}},"type":"pipe|http|subprocess"}}],'
            f'"entree":"...","sortie":"..."}}\n'
            f"JSON only. No explanation."
        )

        resp = self._call([{"role": "user", "content": prompt}], 1500)
        runtime = _extract_json(resp)

        if not runtime:
            runtime = {
                "meta": {"nom": "merged-runtime", "objectif": objective,
                         "langages": [graph_a.get("meta",{}).get("langage","?"),
                                      graph_b.get("meta",{}).get("langage","?")]},
                "modules": {
                    "input":  {"langage": graph_a.get("meta",{}).get("langage","python"),
                               "role": "Input processor"},
                    "output": {"langage": graph_b.get("meta",{}).get("langage","javascript"),
                               "role": "Output generator"},
                },
                "edges":  [{"de": "input", "vers": "output", "type": "pipe"}],
                "entree": "input",
                "sortie": "output",
            }

        return runtime
