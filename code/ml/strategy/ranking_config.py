# -*- coding: utf-8 -*-
"""
Immutable Configuration Container for G.4.5.5 Strategy Optimizer.
"""

from dataclasses import dataclass
from typing import Dict, Any


@dataclass(frozen=True)
class OptimizationConfig:
    """
    Immutable configuration object for strategy ranking and optimization.

    Attributes:
        top_k: Number of top valid strategies to return in final ranking (default: 10).
        ranking_version: Engine version string for tracking and auditability (default: "1.0.0").
    """
    top_k: int = 10
    ranking_version: str = "1.0.0"

    def __post_init__(self):
        """Validate configuration settings."""
        if isinstance(self.top_k, bool) or not isinstance(self.top_k, int):
            raise ValueError(f"top_k must be an integer > 0, got {type(self.top_k).__name__} ({self.top_k})")
        if self.top_k <= 0:
            raise ValueError(f"top_k must be > 0, got {self.top_k}")
        if not self.ranking_version:
            raise ValueError("ranking_version cannot be empty")

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary representation."""
        return {
            "top_k": self.top_k,
            "ranking_version": self.ranking_version,
        }
