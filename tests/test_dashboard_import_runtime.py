# -*- coding: utf-8 -*-
"""
Runtime Import & Streamlit Execution Protection Test.
Ensures that the Streamlit Analytics Dashboard can locate and import
the Strategy Engine (`ml.strategy`) under pure Streamlit runtime conditions
where `code/partie3` is the script root, preventing `No module named 'ml'` regressions.
"""

import sys
import os
import pytest

# Calculate paths relative to repository root
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CODE_DIR = os.path.join(REPO_ROOT, "code")
PARTIE3_DIR = os.path.join(CODE_DIR, "partie3")

def test_streamlit_runtime_import_resolution():
    """Simulates Streamlit runtime entry point where sys.path[0] is code/partie3."""
    # Temporarily set sys.path to simulate Streamlit execution environment
    original_sys_path = list(sys.path)
    try:
        # Streamlit sets script dir as sys.path[0]
        sys.path.insert(0, PARTIE3_DIR)
        
        # Ensure CODE_DIR is inserted as done by analytics_dashboard.py
        if CODE_DIR not in sys.path:
            sys.path.insert(0, CODE_DIR)
            
        # Test imports from ml package
        from ml.strategy import (
            OptimizationConfig, OptimizationCandidate, StrategyOptimizer, StrategyDashboardAdapter
        )
        from ml.strategy.strategy_dashboard import render_strategy_dashboard_tab

        assert StrategyDashboardAdapter is not None
        assert render_strategy_dashboard_tab is not None

        # Instantiate adapter to verify full runtime initialization
        cands = [
            OptimizationCandidate("SCN_001", "SOFT:1-25|MEDIUM:26-52", True, 0, 4800.0, 1, 5.2, 35.0),
            OptimizationCandidate("SCN_002", "MEDIUM:1-28|HARD:29-52", True, 0, 4812.5, 1, 8.0, 28.0),
        ]
        opt = StrategyOptimizer(OptimizationConfig(top_k=2))
        ranking = opt.optimize(cands)

        adapter = StrategyDashboardAdapter(ranking_result=ranking)
        assert adapter is not None
        assert not adapter.ranking_result.is_empty

    finally:
        sys.path = original_sys_path
