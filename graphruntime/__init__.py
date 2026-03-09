"""GraphRuntime — Universal Architecture Graph CLI"""
__version__ = "2.0.0-beta"
__author__  = "Daouda Abdoul Anzize"

from graphruntime.extractor import Extractor
from graphruntime.merger    import Merger
from graphruntime.runner    import Runner

# Re-export agents with correct names
from graphruntime.agents import Modifier, Creator, Rewirer, GoalAgent

__all__ = ["Extractor", "Merger", "Runner", "Modifier", "Creator", "Rewirer", "GoalAgent"]
