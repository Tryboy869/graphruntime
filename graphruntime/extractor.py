"""
GraphRuntime Universal Extractor
Supports 42 languages via the 4 universal questions schema
"""
import json
import os
import re
import requests
import subprocess
import tempfile
from pathlib import Path


SCHEMA = {
    "signaux_entree": [
        "import ", "from ", "require(", "use ", "extern crate",
        "#include", "using ", "include ", "source ", "load(",
        "require_once", "include_once", "@import", "depends_on",
        "data \"", "resource \"", "FROM ", "COPY ", "open ",
    ],
    "signaux_sortie": [
        "class ", "def ", "fn ", "func ", "function ", "export ",
        "pub fn", "pub struct", "pub enum", "pub trait",
        "public class", "public interface", "public func",
        "interface ", "type ", "struct ", "enum ", "trait ",
        "const ", "module.exports", "export default", "export const",
        "export function", "export class", "CREATE TABLE",
        "CREATE VIEW", "message ", "service ", "rpc ",
        "resource ", "output ", "defmodule ", "abstract class",
        "data class", "fun ", "component ", "contract ",
        "@Component", "@Service", "@Controller",
    ],
    "extensions_code": [
        ".py", ".js", ".mjs", ".cjs", ".ts", ".tsx",
        ".java", ".kt", ".kts", ".scala",
        ".c", ".h", ".cpp", ".cc", ".cxx", ".hpp",
        ".cs", ".go", ".rs", ".rb", ".php", ".swift",
        ".ex", ".exs", ".hs", ".lhs", ".ml", ".mli",
        ".lua", ".r", ".R", ".sh", ".bash", ".zsh",
        ".ps1", ".psm1", ".sql", ".gql", ".graphql",
        ".proto", ".tf", ".tfvars", ".dart",
        ".clj", ".cljs", ".fs", ".fsi", ".nim", ".zig", ".sol",
    ],
    "extensions_config": [
        ".json", ".toml", ".yaml", ".yml", ".cfg", ".ini",
        ".xml", ".pom", ".csproj", ".html", ".vue", ".svelte",
    ],
    "ignorer": [
        "__pycache__", ".git", "venv", ".venv", "node_modules",
        "dist", "build", "target", ".next", ".nuxt", "coverage",
        "vendor", ".terraform", ".cache", "bin", "obj", ".idea",
        ".vscode", "*.egg-info",
    ],
    "taille_max_bytes": 500_000,
}

LANG_MAP = {
    ".py": "python", ".js": "javascript", ".mjs": "javascript",
    ".cjs": "javascript", ".ts": "typescript", ".tsx": "typescript",
    ".java": "java", ".kt": "kotlin", ".kts": "kotlin",
    ".scala": "scala", ".c": "c", ".h": "c",
    ".cpp": "cpp", ".cc": "cpp", ".cxx": "cpp", ".hpp": "cpp",
    ".cs": "csharp", ".go": "go", ".rs": "rust",
    ".rb": "ruby", ".php": "php", ".swift": "swift",
    ".ex": "elixir", ".exs": "elixir", ".hs": "haskell",
    ".lua": "lua", ".r": "r", ".R": "r",
    ".sh": "shell", ".bash": "shell", ".zsh": "shell",
    ".ps1": "powershell", ".sql": "sql", ".gql": "graphql",
    ".graphql": "graphql", ".proto": "protobuf",
    ".tf": "terraform", ".tfvars": "terraform",
    ".dart": "dart", ".clj": "clojure", ".fs": "fsharp",
    ".nim": "nim", ".zig": "zig", ".sol": "solidity",
    ".json": "json", ".yaml": "yaml", ".yml": "yaml",
    ".toml": "toml", ".xml": "xml", ".html": "html",
    ".vue": "vue", ".svelte": "svelte", ".css": "css",
    ".scss": "css",
}


class Extractor:
    def __init__(self, max_files: int = 500):
        self.max_files = max_files

    def extract(self, source: str) -> dict:
        """Main entry point — detects source type and extracts graph."""
        if source.startswith("github:"):
            return self._extract_github(source[7:])
        elif source.startswith("pip:"):
            return self._extract_pip(source[4:])
        elif source.startswith("npm:"):
            return self._extract_npm(source[4:])
        elif source.startswith("cargo:"):
            return self._extract_cargo(source[6:])
        else:
            return self._extract_local(source)

    # ── Local ────────────────────────────────────────────────────
    def _extract_local(self, path: str) -> dict:
        root = Path(path).resolve()
        if not root.exists():
            raise FileNotFoundError(f"Path not found: {path}")
        fichiers = self._collect_files(root)
        return self._build_graph(fichiers, root, str(root.name))

    # ── GitHub ───────────────────────────────────────────────────
    def _extract_github(self, repo: str) -> dict:
        with tempfile.TemporaryDirectory() as tmp:
            url = f"https://github.com/{repo}.git"
            subprocess.run(
                ["git", "clone", "--depth=1", url, tmp],
                capture_output=True, check=True
            )
            return self._extract_local(tmp)

    # ── PyPI ─────────────────────────────────────────────────────
    def _extract_pip(self, package: str) -> dict:
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(
                ["pip", "download", package, "--no-deps",
                 "-d", tmp, "--quiet"],
                capture_output=True
            )
            # Find and extract the wheel/sdist
            for f in Path(tmp).iterdir():
                if f.suffix in [".whl", ".tar.gz", ".zip"]:
                    import zipfile, tarfile
                    extract_to = Path(tmp) / "extracted"
                    extract_to.mkdir()
                    try:
                        if f.suffix == ".whl" or f.suffix == ".zip":
                            with zipfile.ZipFile(f) as z:
                                z.extractall(extract_to)
                        else:
                            with tarfile.open(f) as t:
                                t.extractall(extract_to)
                    except Exception:
                        pass
                    return self._extract_local(str(extract_to))
            raise RuntimeError(f"Could not download {package}")

    # ── npm ──────────────────────────────────────────────────────
    def _extract_npm(self, package: str) -> dict:
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(
                ["npm", "pack", package, "--pack-destination", tmp],
                capture_output=True, cwd=tmp
            )
            import tarfile
            for f in Path(tmp).glob("*.tgz"):
                extract_to = Path(tmp) / "extracted"
                extract_to.mkdir()
                with tarfile.open(f) as t:
                    t.extractall(extract_to)
                src = extract_to / "package" / "src"
                if src.exists():
                    return self._extract_local(str(src))
                return self._extract_local(str(extract_to))
            raise RuntimeError(f"Could not download {package}")

    # ── Cargo ────────────────────────────────────────────────────
    def _extract_cargo(self, crate: str) -> dict:
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(
                ["cargo", "download", crate, "-x", "-o", tmp],
                capture_output=True
            )
            return self._extract_local(tmp)

    # ── Core graph building ──────────────────────────────────────
    def _collect_files(self, root: Path) -> list:
        ignorer = set(SCHEMA["ignorer"])
        extensions = set(SCHEMA["extensions_code"] + SCHEMA["extensions_config"])
        fichiers = []

        for path, dirs, files in os.walk(root):
            dirs[:] = [d for d in dirs if d not in ignorer
                       and not d.startswith(".")]
            for f in files:
                p = Path(path) / f
                if (p.suffix in extensions
                        and p.stat().st_size <= SCHEMA["taille_max_bytes"]):
                    fichiers.append(p)
                    if len(fichiers) >= self.max_files:
                        return fichiers
        return fichiers

    def _build_graph(self, fichiers: list, root: Path, project_name: str) -> dict:
        # Index
        noms_index = {}
        for ch in fichiers:
            rel  = str(ch.relative_to(root))
            stem = ch.stem
            noms_index[stem]                     = rel
            noms_index[rel]                      = rel
            noms_index[str(ch.with_suffix(""))]  = rel

        noeuds = {}

        # Q1 + Q2
        for ch in fichiers:
            rel    = str(ch.relative_to(root))
            source = ch.read_text(encoding="utf-8", errors="ignore")
            lignes = source.splitlines()
            entrees, sorties = [], []

            for ligne in lignes:
                s = ligne.strip()
                for sig in SCHEMA["signaux_entree"]:
                    if s.startswith(sig):
                        reste = s[len(sig):].strip()
                        token = re.split(r'[\s(;{\'""]', reste)[0].strip("\"',;")
                        if token and len(token) > 1:
                            entrees.append(token)
                        break
                for sig in SCHEMA["signaux_sortie"]:
                    if s.startswith(sig):
                        reste = s[len(sig):].strip()
                        m = re.match(r"(\w+)", reste)
                        if m:
                            nom = m.group(1)
                            skip = {"self","cls","None","True","False",
                                    "if","else","return","pass","raise",
                                    "from","as","default","async","abstract"}
                            if nom not in skip and len(nom) > 1:
                                sorties.append(sig.strip() + " " + nom)
                        break

            noeuds[rel] = {
                "fichier":         rel,
                "langage":         LANG_MAP.get(ch.suffix, "unknown"),
                "lignes":          len(lignes),
                "taille_bytes":    ch.stat().st_size,
                "entrees":         sorted(set(entrees)),
                "sorties":         sorted(set(sorties)),
                "appelle":         [],
                "est_appele_par":  [],
                "type_noeud":      "standard",
            }

        # Q3
        for rel, noeud in noeuds.items():
            appelle = []
            for entree in noeud["entrees"]:
                cands = [
                    entree,
                    entree.replace(".", "/"),
                    entree.split(".")[-1],
                    entree.lstrip(".").replace(".", "/"),
                ]
                # TypeScript / JS relative import
                if entree.startswith("."):
                    dir_cur = str(Path(rel).parent)
                    resolved = str(Path(dir_cur) / entree)
                    cands += [resolved, resolved + ".ts", resolved + ".js",
                               resolved + "/index.ts", resolved + "/index.js"]

                for c in cands:
                    if c in noms_index and noms_index[c] != rel:
                        cible = noms_index[c]
                        if cible not in appelle:
                            appelle.append(cible)
                        break
            noeud["appelle"] = sorted(set(appelle))

        # Q4
        for rel, noeud in noeuds.items():
            for cible in noeud["appelle"]:
                if cible in noeuds and rel not in noeuds[cible]["est_appele_par"]:
                    noeuds[cible]["est_appele_par"].append(rel)

        for noeud in noeuds.values():
            noeud["est_appele_par"].sort()

        # Edges
        edges = []
        for rel, noeud in noeuds.items():
            for cible in noeud["appelle"]:
                type_e = ("circulaire"
                          if rel in noeuds.get(cible, {}).get("appelle", [])
                          else "interne")
                edges.append({"de": rel, "vers": cible, "type": type_e})

        # Patterns
        patterns = []
        total    = len(noeuds)
        for rel, noeud in noeuds.items():
            nb_in  = len(noeud["est_appele_par"])
            nb_out = len(noeud["appelle"])
            if nb_in >= total * 0.20:
                noeud["type_noeud"] = "hub"
                patterns.append(f"hub → '{rel}' (in={nb_in}, {nb_in/total*100:.0f}% du projet)")
            elif nb_in >= 3 and nb_out >= 2:
                noeud["type_noeud"] = "central"
                patterns.append(f"central → '{rel}' (in={nb_in}, out={nb_out})")
            elif nb_in == 0 and nb_out >= 2:
                noeud["type_noeud"] = "point_entree"
                patterns.append(f"point_entree → '{rel}'")
            elif nb_in >= 3 and nb_out == 0:
                noeud["type_noeud"] = "feuille"
                patterns.append(f"feuille → '{rel}' (in={nb_in})")

        circulaires = [e for e in edges if e["type"] == "circulaire"]
        if circulaires:
            patterns.append(f"circulaire → {len(circulaires)} cycles détectés")

        # Lang distribution
        langs: dict = {}
        for n in noeuds.values():
            l = n["langage"]
            langs[l] = langs.get(l, 0) + 1

        stats = {
            "fichiers_total":     len(noeuds),
            "edges_total":        len(edges),
            "edges_circulaires":  len(circulaires),
            "noeuds_centraux":    len([n for n in noeuds.values() if n["type_noeud"] == "central"]),
            "noeuds_feuilles":    len([n for n in noeuds.values() if n["type_noeud"] == "feuille"]),
            "noeuds_hubs":        len([n for n in noeuds.values() if n["type_noeud"] == "hub"]),
            "points_entree":      len([n for n in noeuds.values() if n["type_noeud"] == "point_entree"]),
            "fichier_plus_appele": max(noeuds.values(),
                                       key=lambda n: len(n["est_appele_par"]),
                                       default={}).get("fichier", "?"),
        }

        return {
            "meta": {
                "projet":  project_name,
                "schema":  "universal-graph-extractor v3.0",
                "langages": langs,
            },
            "stats":    stats,
            "noeuds":   noeuds,
            "edges":    edges,
            "patterns": patterns,
        }
