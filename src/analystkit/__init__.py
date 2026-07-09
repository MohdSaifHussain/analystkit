"""AnalystKit — data quality & analysis toolkit.

DAMA six dimensions, workpaper discipline, self-teaching by design.
v2.0: multi-module src layout (PyPA), read-only database sources
(DuckDB official security guidance), optional AI narrative layer
(official Anthropic SDK) that never touches data.
"""
from analystkit.core import AnalystKitError, Dimension
from analystkit.dedupe import find_duplicates
from analystkit.engine import columns_of, load_source
from analystkit.profiling import ColumnProfile, dimension_scores, profile_columns
from analystkit.reconcile import ReconcileResult, reconcile_sources
from analystkit.rules import RuleResult, load_rules, run_rules

__version__ = "2.0.0"

__all__ = [
    "AnalystKitError",
    "ColumnProfile",
    "Dimension",
    "ReconcileResult",
    "RuleResult",
    "__version__",
    "columns_of",
    "dimension_scores",
    "find_duplicates",
    "load_rules",
    "load_source",
    "profile_columns",
    "reconcile_sources",
    "run_rules",
]
