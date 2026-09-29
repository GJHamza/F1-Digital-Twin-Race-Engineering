# -*- coding: utf-8 -*-
"""
Strategy Dashboard Presentation Module for G.4.6.2, G.4.6.3, G.4.6.4, and G.4.6.5.
Provides pure view-model data preparation and Streamlit UI components
for presenting Top-K strategy optimization rankings, trade-off comparisons,
stint/compound race timelines, and single-strategy fuel & 4-corner tire analytics
without re-ranking or mutating upstream domain objects.
"""

import math
from typing import Dict, Any, Optional, List, Sequence, Tuple
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

from ml.strategy.dashboard_adapter import StrategyDashboardAdapter
from ml.strategy.ranking_result import RankingResult
from ml.strategy.config import (
    DEFAULT_TOTAL_LAPS,
    DEFAULT_STARTING_FUEL_KG,
    DEFAULT_PIT_STOP_LOSS_SEC,
    DEFAULT_MAX_TIRE_WEAR_PCT,
    DEFAULT_MIN_STINT_LAPS,
)

MAX_DEFAULT_COMPARISON_COUNT = 4
AUTHORITATIVE_MAX_TIRE_WEAR_LIMIT = 85.0  # G.4.5.4 hard constraint limit (%)
DEFAULT_FIA_FUEL_RESERVE_KG = 1.0         # Default FIA mandatory fuel reserve (kg)

# Official F1 Compound Color Palette for Gantt Timeline & Charts
COMPOUND_COLOR_MAP = {
    "SOFT": "#FF1801",        # Red
    "MEDIUM": "#FFF200",      # Yellow
    "HARD": "#E6E6E6",        # Light Slate / White
    "INTERMEDIATE": "#39B54A",# Green
    "WET": "#00AEEF",         # Blue
}


def prepare_leaderboard_view_data(
    adapter: StrategyDashboardAdapter,
    max_rank_filter: Optional[int] = None,
    scenario_search: Optional[str] = None,
    pit_stop_filter: Optional[int] = None,
    warning_only_filter: bool = False,
) -> Dict[str, Any]:
    """
    Prepares pure presentation view-data dictionary for the Strategy Leaderboard (G.4.6.2).
    Performs view-level filtering ONLY without modifying upstream RankingResult or re-ranking.
    """
    if adapter is None:
        raise ValueError("adapter cannot be None")

    ranking_res: RankingResult = adapter.ranking_result

    summary = {
        "leader_scenario_id": ranking_res.leader_scenario_id if not ranking_res.is_empty else None,
        "leader_race_time_sec": ranking_res.leader_race_time_sec if not ranking_res.is_empty else None,
        "total_candidates": ranking_res.total_candidates,
        "valid_candidates": ranking_res.valid_candidates,
        "excluded_candidates": ranking_res.excluded_candidates,
        "top_k": ranking_res.top_k,
        "is_empty": ranking_res.is_empty,
    }

    if ranking_res.is_empty:
        empty_df = adapter.leaderboard_dataframe()
        return {
            "summary": summary,
            "leaderboard_df": empty_df,
            "total_displayed": 0,
        }

    df = adapter.leaderboard_dataframe()

    filtered_df = df.copy()

    if max_rank_filter is not None and max_rank_filter > 0:
        filtered_df = filtered_df[filtered_df["rank"] <= max_rank_filter]

    if scenario_search:
        query = scenario_search.strip().upper()
        mask = (
            filtered_df["scenario_id"].str.upper().str.contains(query, regex=False) |
            filtered_df["canonical_key"].str.upper().str.contains(query, regex=False)
        )
        filtered_df = filtered_df[mask]

    if pit_stop_filter is not None and pit_stop_filter >= 0:
        filtered_df = filtered_df[filtered_df["pit_stop_count"] == pit_stop_filter]

    if warning_only_filter:
        filtered_df = filtered_df[filtered_df["warning_count"] > 0]

    display_df = filtered_df.copy()
    display_df["delta_to_leader_sec_fmt"] = display_df["delta_to_leader_sec"].apply(
        lambda d: f"+{d:.3f}" if d > 0 else "0.000"
    )

    return {
        "summary": summary,
        "leaderboard_df": display_df,
        "total_displayed": len(display_df),
    }


def prepare_comparison_view_data(
    adapter: StrategyDashboardAdapter,
    scenario_ids: Optional[Sequence[str]] = None,
    max_compare: int = MAX_DEFAULT_COMPARISON_COUNT,
) -> Dict[str, Any]:
    """
    Prepares pure presentation view-data for Strategy Comparison & Trade-off Analysis (G.4.6.3).
    Limits selection to `max_compare` strategies, preserves upstream ranking order, and collects
    available stint and lap telemetry.
    """
    if adapter is None:
        raise ValueError("adapter cannot be None")

    ranking_res: RankingResult = adapter.ranking_result
    leader_id = ranking_res.leader_scenario_id if not ranking_res.is_empty else None

    if ranking_res.is_empty:
        return {
            "comparison_df": pd.DataFrame(),
            "stint_df_map": {},
            "lap_df_map": {},
            "leader_scenario_id": None,
            "leader_included": False,
            "selected_scenario_ids": [],
        }

    all_ranked_ids = [s.scenario_id for s in ranking_res.ranked_strategies]

    if scenario_ids:
        seen = set()
        requested_ids = []
        for sid in scenario_ids:
            if sid and sid not in seen:
                seen.add(sid)
                requested_ids.append(sid)

        selected_ids = requested_ids[:max_compare]
    else:
        selected_ids = all_ranked_ids[:max_compare]

    for sid in selected_ids:
        if sid not in all_ranked_ids:
            raise ValueError(f"Scenario ID '{sid}' not found in ranking result")

    comp_df = adapter.comparison_dataframe(selected_ids)

    stint_df_map = {}
    lap_df_map = {}

    for sid in selected_ids:
        try:
            stint_df_map[sid] = adapter.stint_dataframe(sid)
        except (ValueError, KeyError, AttributeError):
            stint_df_map[sid] = pd.DataFrame()

        try:
            lap_df_map[sid] = adapter.lap_dataframe(sid)
        except (ValueError, KeyError, AttributeError):
            lap_df_map[sid] = pd.DataFrame()

    leader_included = leader_id in selected_ids if leader_id else False

    return {
        "comparison_df": comp_df,
        "stint_df_map": stint_df_map,
        "lap_df_map": lap_df_map,
        "leader_scenario_id": leader_id,
        "leader_included": leader_included,
        "selected_scenario_ids": selected_ids,
    }


def prepare_stint_timeline_data(
    adapter: StrategyDashboardAdapter,
    scenario_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Prepares pure presentation view-data for the Strategy Stint / Compound Timeline (G.4.6.4).
    """
    if adapter is None:
        raise ValueError("adapter cannot be None")

    ranking_res: RankingResult = adapter.ranking_result
    if ranking_res.is_empty:
        return {
            "summary": {},
            "stint_df": pd.DataFrame(),
            "pit_df": pd.DataFrame(),
            "timeline_df": pd.DataFrame(),
            "is_empty": True,
            "scenario_id": None,
        }

    if scenario_id is None:
        scenario_id = ranking_res.leader_scenario_id or ranking_res.ranked_strategies[0].scenario_id

    strat_df = adapter.selected_strategy_dataframe(scenario_id)
    strat_row = strat_df.iloc[0]

    is_leader = (scenario_id == ranking_res.leader_scenario_id)

    summary = {
        "scenario_id": scenario_id,
        "rank": int(strat_row["rank"]),
        "total_race_time_sec": float(strat_row["total_race_time_sec"]),
        "delta_to_leader_sec": float(strat_row["delta_to_leader_sec"]),
        "pit_stop_count": int(strat_row["pit_stop_count"]),
        "final_fuel_kg": float(strat_row["final_fuel_kg"]),
        "avg_final_tire_wear_pct": float(strat_row["avg_final_tire_wear_pct"]),
        "warning_count": int(strat_row["warning_count"]),
        "canonical_key": str(strat_row["canonical_key"]),
        "is_leader": is_leader,
        "leader_scenario_id": ranking_res.leader_scenario_id,
    }

    try:
        stint_df = adapter.stint_dataframe(scenario_id).copy()
    except (ValueError, KeyError, AttributeError):
        stint_df = pd.DataFrame()

    try:
        pit_df = adapter.pit_dataframe(scenario_id).copy()
    except (ValueError, KeyError, AttributeError):
        pit_df = pd.DataFrame()

    if "stint_laps" not in stint_df.columns and not stint_df.empty:
        stint_df["stint_laps"] = (stint_df["end_lap"] - stint_df["start_lap"]) + 1

    summary["number_of_stints"] = len(stint_df)

    timeline_records = []
    pit_map = {}
    if not pit_df.empty and "pit_lap" in pit_df.columns:
        for _, p_row in pit_df.iterrows():
            stint_b = int(p_row.get("stint_before", 0))
            p_lap = int(p_row["pit_lap"])
            p_dur = float(p_row.get("duration_sec", 0.0))
            pit_map[stint_b] = f"Lap {p_lap} ({p_dur:.1f}s)"

    for _, s_row in stint_df.iterrows():
        s_num = int(s_row["stint_number"])
        comp = str(s_row["compound"]).upper()
        start = int(s_row["start_lap"])
        end = int(s_row["end_lap"])
        s_laps = int(s_row.get("stint_laps", (end - start) + 1))
        pit_tr = pit_map.get(s_num, "—")

        rec = {
            "scenario_id": scenario_id,
            "stint_number": s_num,
            "stint_label": f"Stint {s_num}: {comp}",
            "compound": comp,
            "start_lap": start,
            "end_lap": end,
            "stint_laps": s_laps,
            "pit_transition": pit_tr,
            "color": COMPOUND_COLOR_MAP.get(comp, "#888888"),
        }
        for col in ["starting_fuel", "ending_fuel", "fuel_consumed", "starting_wear", "ending_wear"]:
            if col in s_row:
                rec[col] = float(s_row[col])

        timeline_records.append(rec)

    timeline_df = pd.DataFrame(timeline_records)

    try:
        val_df = adapter.validation_dataframe(scenario_id)
        summary["validation_status"] = "VALID" if bool(val_df.iloc[0].get("valid", True)) else "INVALID"
    except (ValueError, KeyError, AttributeError):
        summary["validation_status"] = "VALID"

    return {
        "summary": summary,
        "stint_df": stint_df,
        "pit_df": pit_df,
        "timeline_df": timeline_df,
        "is_empty": False,
        "scenario_id": scenario_id,
        "compound_colors": COMPOUND_COLOR_MAP,
    }


def prepare_fuel_tire_analytics_view_data(
    adapter: StrategyDashboardAdapter,
    scenario_id: Optional[str] = None,
    reserve_threshold_kg: float = DEFAULT_FIA_FUEL_RESERVE_KG,
) -> Dict[str, Any]:
    """
    Prepares pure presentation view-data for Fuel & Tire Analytics (G.4.6.5).
    Operates on a SINGLE selected strategy, calculating fuel burn rate, safety margins,
    4-corner wheel degradation, axle/lateral wear balance, stint degradation rates,
    and remaining tire life projections without modifying domain objects.

    Args:
        adapter: StrategyDashboardAdapter instance.
        scenario_id: Canonical scenario ID. Defaults to leader if None.
        reserve_threshold_kg: Mandatory fuel reserve threshold in kg (default 1.0 kg).

    Returns:
        Dict containing fuel summary, corner wear DataFrame, balance metrics, stint deg rates, alerts.
    """
    if adapter is None:
        raise ValueError("adapter cannot be None")

    ranking_res: RankingResult = adapter.ranking_result
    if ranking_res.is_empty:
        return {
            "summary": {},
            "corner_wear_df": pd.DataFrame(),
            "stint_analytics_df": pd.DataFrame(),
            "balance": {},
            "alerts": [],
            "is_empty": True,
            "scenario_id": None,
        }

    all_ranked_ids = [s.scenario_id for s in ranking_res.ranked_strategies]

    if scenario_id is None:
        scenario_id = ranking_res.leader_scenario_id or all_ranked_ids[0]

    if scenario_id not in all_ranked_ids:
        raise ValueError(f"Scenario ID '{scenario_id}' not found in ranking result")

    # 1. Selected Strategy Base Metrics
    strat_df = adapter.selected_strategy_dataframe(scenario_id)
    strat_row = strat_df.iloc[0]

    rank = int(strat_row["rank"])
    final_fuel_kg = float(strat_row["final_fuel_kg"])
    avg_final_wear = float(strat_row["avg_final_tire_wear_pct"])
    total_race_time = float(strat_row["total_race_time_sec"])
    delta_to_leader = float(strat_row["delta_to_leader_sec"])
    is_leader = (scenario_id == ranking_res.leader_scenario_id)

    # 2. Fetch lap & stint DataFrames safely
    try:
        lap_df = adapter.lap_dataframe(scenario_id).copy()
    except (ValueError, KeyError, AttributeError):
        lap_df = pd.DataFrame()

    try:
        stint_df = adapter.stint_dataframe(scenario_id).copy()
    except (ValueError, KeyError, AttributeError):
        stint_df = pd.DataFrame()

    # 3. Fuel Analytics Derivation
    total_laps = len(lap_df) if not lap_df.empty else (int(stint_df["end_lap"].max()) if not stint_df.empty else 50)

    # Determine starting fuel mass
    if not stint_df.empty and "starting_fuel" in stint_df.columns:
        starting_fuel_kg = float(stint_df["starting_fuel"].iloc[0])
    elif not lap_df.empty and "fuel_kg" in lap_df.columns and "fuel_consumed_kg" in lap_df.columns:
        starting_fuel_kg = float(lap_df["fuel_kg"].iloc[0] + lap_df["fuel_consumed_kg"].iloc[0])
    else:
        starting_fuel_kg = float(final_fuel_kg + 95.0)  # Presentation default estimate

    total_fuel_consumed_kg = max(0.0, starting_fuel_kg - final_fuel_kg)
    avg_fuel_burn_rate_kg_lap = (total_fuel_consumed_kg / total_laps) if total_laps > 0 else 0.0
    fuel_safety_margin_kg = final_fuel_kg - reserve_threshold_kg

    if fuel_safety_margin_kg >= 1.0:
        fuel_reserve_status = "SAFE"
    elif fuel_safety_margin_kg >= 0.0:
        fuel_reserve_status = "CAUTION"
    else:
        fuel_reserve_status = "CRITICAL"

    # 4. 4-Corner Wheel Wear & Balance Analytics
    has_corner_data = not lap_df.empty and all(c in lap_df.columns for c in ["tire_wear_fl", "tire_wear_fr", "tire_wear_rl", "tire_wear_rr"])

    if has_corner_data:
        fl = float(lap_df["tire_wear_fl"].iloc[-1])
        fr = float(lap_df["tire_wear_fr"].iloc[-1])
        rl = float(lap_df["tire_wear_rl"].iloc[-1])
        rr = float(lap_df["tire_wear_rr"].iloc[-1])
        corner_wear_df = lap_df[["lap_number", "tire_wear_fl", "tire_wear_fr", "tire_wear_rl", "tire_wear_rr", "avg_tire_wear"]].copy()
    else:
        fl = fr = rl = rr = avg_final_wear
        corner_wear_df = pd.DataFrame()

    most_worn = max([("FL", fl), ("FR", fr), ("RL", rl), ("RR", rr)], key=lambda x: x[1])
    max_corner_wear_pct = float(most_worn[1])
    most_worn_wheel = str(most_worn[0])

    front_avg = (fl + fr) / 2.0
    rear_avg = (rl + rr) / 2.0
    left_avg = (fl + rl) / 2.0
    right_avg = (fr + rr) / 2.0

    front_rear_delta = front_avg - rear_avg
    left_right_delta = left_avg - right_avg

    if rear_avg > 0:
        front_rear_ratio = front_avg / rear_avg
    else:
        front_rear_ratio = 1.0 if front_avg == 0 else float("nan")

    if right_avg > 0:
        left_right_ratio = left_avg / right_avg
    else:
        left_right_ratio = 1.0 if left_avg == 0 else float("nan")

    balance = {
        "front_avg_wear": front_avg,
        "rear_avg_wear": rear_avg,
        "left_avg_wear": left_avg,
        "right_avg_wear": right_avg,
        "front_rear_delta": front_rear_delta,
        "left_right_delta": left_right_delta,
        "front_rear_ratio": front_rear_ratio,
        "left_right_ratio": left_right_ratio,
        "is_imbalanced": (abs(front_rear_delta) > 5.0 or abs(left_right_delta) > 5.0),
    }

    # 5. Stint Degradation & Remaining Tire Life Projections
    stint_analytics_records = []
    max_deg_rate = 0.0

    if not stint_df.empty:
        for _, s_row in stint_df.iterrows():
            s_num = int(s_row["stint_number"])
            comp = str(s_row["compound"]).upper()
            start = int(s_row["start_lap"])
            end = int(s_row["end_lap"])
            s_laps = int(s_row.get("stint_laps", (end - start) + 1))
            s_wear = float(s_row.get("starting_wear", 0.0))
            e_wear = float(s_row.get("ending_wear", avg_final_wear))
            wear_delta = max(0.0, e_wear - s_wear)
            deg_rate = (wear_delta / s_laps) if s_laps > 0 else 0.0
            max_deg_rate = max(max_deg_rate, deg_rate)

            # Estimated remaining laps before reaching 85% limit
            capacity_left = max(0.0, AUTHORITATIVE_MAX_TIRE_WEAR_LIMIT - e_wear)
            if deg_rate > 0.0:
                est_rem_laps = int(capacity_left / deg_rate)
                rem_laps_str = f"{est_rem_laps} laps"
            else:
                est_rem_laps = None
                rem_laps_str = "Projection unavailable"

            stint_analytics_records.append({
                "stint_number": s_num,
                "compound": comp,
                "start_lap": start,
                "end_lap": end,
                "stint_laps": s_laps,
                "starting_wear": s_wear,
                "ending_wear": e_wear,
                "wear_delta": wear_delta,
                "degradation_pct_per_lap": deg_rate,
                "estimated_remaining_laps": est_rem_laps,
                "remaining_laps_display": rem_laps_str,
            })

    stint_analytics_df = pd.DataFrame(stint_analytics_records)

    # 6. Engineering Alert Badges
    alerts = []
    # Fuel alert
    if fuel_reserve_status == "CRITICAL":
        alerts.append({"category": "FUEL", "severity": "CRITICAL", "message": f"CRITICAL FUEL: Reserve ({fuel_safety_margin_kg:.2f} kg) below regulatory limit!"})
    elif fuel_reserve_status == "CAUTION":
        alerts.append({"category": "FUEL", "severity": "WARNING", "message": f"LOW FUEL MARGIN: Only {fuel_safety_margin_kg:.2f} kg reserve remaining above minimum threshold."})
    else:
        alerts.append({"category": "FUEL", "severity": "NORMAL", "message": f"FUEL SAFE: {final_fuel_kg:.2f} kg remaining ({fuel_safety_margin_kg:.2f} kg safety reserve)."})

    # Tire wear alert
    if max_corner_wear_pct >= AUTHORITATIVE_MAX_TIRE_WEAR_LIMIT:
        alerts.append({"category": "TIRE WEAR", "severity": "CRITICAL", "message": f"HIGH TIRE WEAR CLIFF: {most_worn_wheel} wheel hit limit ({max_corner_wear_pct:.1f}% >= {AUTHORITATIVE_MAX_TIRE_WEAR_LIMIT:.1f}%)!"})
    elif max_corner_wear_pct >= 75.0:
        alerts.append({"category": "TIRE WEAR", "severity": "WARNING", "message": f"TIRE DEGRADATION WARNING: {most_worn_wheel} wheel at {max_corner_wear_pct:.1f}% wear."})
    else:
        alerts.append({"category": "TIRE WEAR", "severity": "NORMAL", "message": f"TIRE WEAR NORMAL: Max wheel wear at {max_corner_wear_pct:.1f}% ({most_worn_wheel})."})

    # Balance alert
    if balance["is_imbalanced"]:
        alerts.append({"category": "BALANCE", "severity": "WARNING", "message": f"TIRE BIAS IMBALANCE: Front/Rear delta {front_rear_delta:+.1f}%, Left/Right delta {left_right_delta:+.1f}%."})
    else:
        alerts.append({"category": "BALANCE", "severity": "NORMAL", "message": "AXLE BALANCE OPTIMAL: Even degradation between front/rear axles and left/right sides."})

    # Summary dictionary
    summary = {
        "scenario_id": scenario_id,
        "rank": rank,
        "is_leader": is_leader,
        "leader_scenario_id": ranking_res.leader_scenario_id,
        "total_race_time_sec": total_race_time,
        "delta_to_leader_sec": delta_to_leader,
        "starting_fuel_kg": starting_fuel_kg,
        "final_fuel_kg": final_fuel_kg,
        "total_fuel_consumed_kg": total_fuel_consumed_kg,
        "avg_fuel_burn_rate_kg_lap": avg_fuel_burn_rate_kg_lap,
        "fuel_safety_margin_kg": fuel_safety_margin_kg,
        "fuel_reserve_status": fuel_reserve_status,
        "fl_final_wear": fl,
        "fr_final_wear": fr,
        "rl_final_wear": rl,
        "rr_final_wear": rr,
        "avg_final_tire_wear_pct": avg_final_wear,
        "max_corner_wear_pct": max_corner_wear_pct,
        "most_worn_wheel": most_worn_wheel,
        "max_degradation_rate_pct_lap": max_deg_rate,
        "total_laps": total_laps,
    }

    return {
        "summary": summary,
        "corner_wear_df": corner_wear_df,
        "stint_analytics_df": stint_analytics_df,
        "balance": balance,
        "alerts": alerts,
        "is_empty": False,
        "scenario_id": scenario_id,
    }


def render_strategy_leaderboard(adapter: StrategyDashboardAdapter) -> Optional[str]:
    """
    Renders the interactive Streamlit Strategy Leaderboard UI component (G.4.6.2).
    """
    st.markdown("## STRATEGY LEADERBOARD")

    if adapter is None or adapter.ranking_result.is_empty:
        st.info("No valid strategies available in current ranking result.")
        return None

    ranking_res = adapter.ranking_result

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.metric(
            label="WINNING STRATEGY",
            value=ranking_res.leader_scenario_id or "N/A",
        )
    with c2:
        leader_time_str = f"{ranking_res.leader_race_time_sec:.2f} s" if ranking_res.leader_race_time_sec else "N/A"
        st.metric(
            label="LEADER RACE TIME",
            value=leader_time_str,
        )
    with c3:
        st.metric(
            label="EVALUATED SPACE",
            value=f"{ranking_res.total_candidates:,}",
        )
    with c4:
        st.metric(
            label="VALID STRATEGIES",
            value=f"{ranking_res.valid_candidates:,}",
        )
    with c5:
        st.metric(
            label="EXCLUDED CANDIDATES",
            value=f"{ranking_res.excluded_candidates:,}",
        )

    st.markdown("---")

    with st.expander("Strategy Filters & Search Options", expanded=False):
        fc1, fc2, fc3 = st.columns(3)
        with fc1:
            scenario_search = st.text_input("Search Scenario / Compound", placeholder="e.g. SOFT or SCN_...")
        with fc2:
            max_stops = max([s.pit_stop_count for s in ranking_res.ranked_strategies] or [3])
            pit_stop_filter_val = st.selectbox(
                "Filter Pit Stops",
                options=["All"] + list(range(0, max_stops + 1)),
                index=0,
            )
            pit_stop_filter = None if pit_stop_filter_val == "All" else int(pit_stop_filter_val)
        with fc3:
            warning_only = st.checkbox("Show Warnings Only", value=False)

    view_data = prepare_leaderboard_view_data(
        adapter=adapter,
        scenario_search=scenario_search,
        pit_stop_filter=pit_stop_filter,
        warning_only_filter=warning_only,
    )

    df_display = view_data["leaderboard_df"]

    if df_display.empty:
        st.warning("No strategies match the applied filters.")
        return None

    render_df = df_display[[
        "rank",
        "scenario_id",
        "canonical_key",
        "total_race_time_sec",
        "delta_to_leader_sec_fmt",
        "pit_stop_count",
        "final_fuel_kg",
        "avg_final_tire_wear_pct",
        "warning_count",
    ]].copy()

    render_df.columns = [
        "Rank",
        "Scenario ID",
        "Strategy Sequence",
        "Race Time (s)",
        "Δ Leader (s)",
        "Pit Stops",
        "Fuel Left (kg)",
        "Avg Wear (%)",
        "Warnings",
    ]

    st.dataframe(
        render_df,
        use_container_width=True,
        hide_index=True,
    )

    scen_options = list(df_display["scenario_id"])
    default_id = scen_options[0] if scen_options else None

    if "selected_scenario_id" not in st.session_state:
        st.session_state["selected_scenario_id"] = default_id

    selected_id = st.selectbox(
        "Select Strategy for Detailed Inspection & Telemetry Analytics:",
        options=scen_options,
        index=0 if default_id in scen_options else 0,
        key="leaderboard_strategy_selectbox",
    )

    st.session_state["selected_scenario_id"] = selected_id
    return selected_id


def render_strategy_comparison(
    adapter: StrategyDashboardAdapter,
    default_selected_ids: Optional[List[str]] = None,
) -> List[str]:
    """
    Renders the Strategy Comparison & Trade-off Analysis UI component (G.4.6.3).
    """
    st.markdown("## STRATEGY TRADE-OFF & COMPARISON")

    if adapter is None or adapter.ranking_result.is_empty:
        st.info("No strategies available for comparison.")
        return []

    ranking_res = adapter.ranking_result
    all_scenario_ids = [s.scenario_id for s in ranking_res.ranked_strategies]

    if "comparison_scenario_ids" not in st.session_state:
        if default_selected_ids:
            st.session_state["comparison_scenario_ids"] = default_selected_ids[:MAX_DEFAULT_COMPARISON_COUNT]
        else:
            st.session_state["comparison_scenario_ids"] = all_scenario_ids[:MAX_DEFAULT_COMPARISON_COUNT]

    selected_ids = st.multiselect(
        label="Select Strategies to Compare (Max 4):",
        options=all_scenario_ids,
        default=st.session_state["comparison_scenario_ids"],
        max_selections=MAX_DEFAULT_COMPARISON_COUNT,
        key="strategy_comparison_multiselect",
    )

    st.session_state["comparison_scenario_ids"] = selected_ids

    if not selected_ids:
        st.warning("Select at least one strategy to display comparison analytics.")
        return []

    comp_data = prepare_comparison_view_data(
        adapter=adapter,
        scenario_ids=selected_ids,
        max_compare=MAX_DEFAULT_COMPARISON_COUNT,
    )

    if not comp_data["leader_included"] and comp_data["leader_scenario_id"]:
        st.info(
            f"Authoritative leader (`{comp_data['leader_scenario_id']}`) is not included in current comparison selection."
        )

    comp_df = comp_data["comparison_df"].copy()
    if not comp_df.empty:
        comp_display = comp_df.copy()
        comp_display["delta_to_leader_sec_fmt"] = comp_display["delta_to_leader_sec"].apply(
            lambda d: f"+{d:.3f} s" if d > 0 else "0.000 s (Leader)"
        )

        table_render = comp_display[[
            "rank",
            "scenario_id",
            "canonical_key",
            "total_race_time_sec",
            "delta_to_leader_sec_fmt",
            "pit_stop_count",
            "final_fuel_kg",
            "avg_final_tire_wear_pct",
            "warning_count",
        ]].copy()

        table_render.columns = [
            "Rank",
            "Scenario ID",
            "Strategy Sequence",
            "Race Time (s)",
            "Δ Leader (s)",
            "Pit Stops",
            "Fuel Left (kg)",
            "Avg Wear (%)",
            "Warnings",
        ]

        st.subheader("Metrics Comparison Matrix")
        st.dataframe(table_render, use_container_width=True, hide_index=True)

    st.subheader("Trade-off Analysis Charts")

    col_chart1, col_chart2, col_chart3 = st.columns(3)

    with col_chart1:
        st.markdown("**Race Time vs. Final Fuel**")
        if not comp_df.empty:
            fig1 = px.scatter(
                comp_df,
                x="final_fuel_kg",
                y="total_race_time_sec",
                color="scenario_id",
                text="scenario_id",
                labels={"final_fuel_kg": "Final Fuel (kg)", "total_race_time_sec": "Total Race Time (s)"},
                color_discrete_sequence=["#0066FF", "#22C55E", "#F59E0B", "#EF4444"]
            )
            fig1.update_traces(marker=dict(size=12), textposition="top center")
            fig1.update_layout(
                plot_bgcolor='#1e293b',
                paper_bgcolor='rgba(0,0,0,0)',
                font=dict(color='#f8fafc', family='JetBrains Mono', size=10),
                margin=dict(l=20, r=20, t=10, b=10),
                height=280,
                showlegend=False
            )
            st.plotly_chart(fig1, use_container_width=True)

    with col_chart2:
        st.markdown("**Race Time vs. Average Wear**")
        if not comp_df.empty:
            fig2 = px.scatter(
                comp_df,
                x="avg_final_tire_wear_pct",
                y="total_race_time_sec",
                color="scenario_id",
                text="scenario_id",
                labels={"avg_final_tire_wear_pct": "Avg Tire Wear (%)", "total_race_time_sec": "Total Race Time (s)"},
                color_discrete_sequence=["#0066FF", "#22C55E", "#F59E0B", "#EF4444"]
            )
            fig2.update_traces(marker=dict(size=12), textposition="top center")
            fig2.update_layout(
                plot_bgcolor='#1e293b',
                paper_bgcolor='rgba(0,0,0,0)',
                font=dict(color='#f8fafc', family='JetBrains Mono', size=10),
                margin=dict(l=20, r=20, t=10, b=10),
                height=280,
                showlegend=False
            )
            st.plotly_chart(fig2, use_container_width=True)

    with col_chart3:
        st.markdown("**Pit Stop Strategy Distribution**")
        if not comp_df.empty:
            fig3 = px.bar(
                comp_df,
                x="scenario_id",
                y="pit_stop_count",
                color="scenario_id",
                labels={"scenario_id": "Scenario ID", "pit_stop_count": "Pit Stop Count"},
                color_discrete_sequence=["#0066FF", "#22C55E", "#F59E0B", "#EF4444"]
            )
            fig3.update_layout(
                plot_bgcolor='#1e293b',
                paper_bgcolor='rgba(0,0,0,0)',
                font=dict(color='#f8fafc', family='JetBrains Mono', size=10),
                margin=dict(l=20, r=20, t=10, b=10),
                height=280,
                showlegend=False
            )
            st.plotly_chart(fig3, use_container_width=True)

    return selected_ids


def render_stint_timeline(
    adapter: StrategyDashboardAdapter,
    scenario_id: Optional[str] = None,
) -> Optional[str]:
    """
    Renders the Strategy Stint / Compound Timeline UI component (G.4.6.4).
    """
    st.markdown("## STINT PLAN & COMPOUND TIMELINE")

    if adapter is None or adapter.ranking_result.is_empty:
        st.info("Stint timeline unavailable for empty ranking result.")
        return None

    timeline_data = prepare_stint_timeline_data(adapter, scenario_id=scenario_id)
    if timeline_data.get("is_empty", False):
        st.warning("Stint timeline unavailable for selected strategy.")
        return None

    summary = timeline_data["summary"]
    scen_id = summary["scenario_id"]

    sc1, sc2, sc3, sc4, sc5, sc6 = st.columns(6)
    with sc1:
        leader_badge = " (LEADER)" if summary["is_leader"] else ""
        st.metric(
            label="SCENARIO ID",
            value=f"#{summary['rank']}{leader_badge}",
            delta=scen_id,
        )
    with sc2:
        st.metric(
            label="RACE TIME",
            value=f"{summary['total_race_time_sec']:.2f} s",
            delta=f"+{summary['delta_to_leader_sec']:.3f} s" if summary['delta_to_leader_sec'] > 0 else "Leader",
        )
    with sc3:
        st.metric(
            label="STINTS / PITS",
            value=f"{summary['number_of_stints']} / {summary['pit_stop_count']}",
        )
    with sc4:
        st.metric(
            label="FUEL REMAINING",
            value=f"{summary['final_fuel_kg']:.2f} kg",
        )
    with sc5:
        st.metric(
            label="AVG TIRE WEAR",
            value=f"{summary['avg_final_tire_wear_pct']:.2f} %",
        )
    with sc6:
        status_str = "VALID" if summary["validation_status"] == "VALID" else "INVALID"
        st.metric(
            label="VALIDATION",
            value=status_str,
            delta=f"{summary['warning_count']} warnings",
        )

    st.markdown(f"**Strategy Pattern:** `{summary['canonical_key']}`")
    st.markdown("---")

    t_df = timeline_data["timeline_df"]
    if not t_df.empty:
        st.subheader("Compound Stint Execution")
        fig_gantt = px.bar(
            t_df,
            x="stint_laps",
            y="stint_label",
            color="compound",
            orientation="h",
            labels={"stint_laps": "Stint Duration (Laps)", "stint_label": "Stint", "compound": "Compound"},
            color_discrete_map=COMPOUND_COLOR_MAP,
            text="compound"
        )
        fig_gantt.update_layout(
            plot_bgcolor='#1e293b',
            paper_bgcolor='rgba(0,0,0,0)',
            font=dict(color='#f8fafc', family='JetBrains Mono', size=10),
            margin=dict(l=20, r=20, t=10, b=10),
            height=220,
            showlegend=True
        )
        st.plotly_chart(fig_gantt, use_container_width=True)

    st.subheader("Stint Breakdown Matrix")
    stint_df = timeline_data["stint_df"]
    if not stint_df.empty:
        display_stints = t_df[[
            "stint_number",
            "compound",
            "start_lap",
            "end_lap",
            "stint_laps",
            "pit_transition",
        ]].copy()

        display_stints.columns = [
            "Stint",
            "Compound",
            "Start Lap",
            "End Lap",
            "Stint Laps",
            "Pit Transition",
        ]

        st.dataframe(display_stints, use_container_width=True, hide_index=True)

    return scen_id


def render_fuel_tire_analytics(
    adapter: StrategyDashboardAdapter,
    scenario_id: Optional[str] = None,
) -> Optional[str]:
    """
    Renders the Single-Strategy Fuel & 4-Corner Tire Telemetry Analytics UI component (G.4.6.5).

    Args:
        adapter: StrategyDashboardAdapter instance.
        scenario_id: Optional scenario ID to inspect.

    Returns:
        Inspected scenario_id string.
    """
    st.markdown("## FUEL & TIRE TELEMETRY ANALYTICS")

    if adapter is None or adapter.ranking_result.is_empty:
        st.info("Fuel & tire analytics unavailable for empty ranking result.")
        return None

    analytics = prepare_fuel_tire_analytics_view_data(adapter, scenario_id=scenario_id)
    if analytics.get("is_empty", False):
        st.warning("Analytics unavailable for selected strategy.")
        return None

    summary = analytics["summary"]
    scen_id = summary["scenario_id"]

    # 1. SECTION 1: ENGINEERING ALERT CARDS
    st.subheader("Engineering Threshold Alerts")
    alert_cols = st.columns(len(analytics["alerts"]))
    for idx, alert in enumerate(analytics["alerts"]):
        with alert_cols[idx]:
            sev = alert["severity"]
            if sev == "CRITICAL":
                st.error(f"**[{alert['category']}]** {alert['message']}")
            elif sev == "WARNING":
                st.warning(f"**[{alert['category']}]** {alert['message']}")
            else:
                st.success(f"**[{alert['category']}]** {alert['message']}")

    st.markdown("---")

    # 2. SECTION 2: FUEL BURN EFFICIENCY & RESERVES
    st.subheader("Fuel Burn Efficiency & Safety Reserve Margins")
    fc1, fc2, fc3, fc4, fc5 = st.columns(5)
    with fc1:
        st.metric("STARTING FUEL", f"{summary['starting_fuel_kg']:.2f} kg")
    with fc2:
        st.metric("FINAL FUEL REMAINING", f"{summary['final_fuel_kg']:.2f} kg")
    with fc3:
        st.metric("TOTAL CONSUMED", f"{summary['total_fuel_consumed_kg']:.2f} kg")
    with fc4:
        st.metric("AVG BURN RATE", f"{summary['avg_fuel_burn_rate_kg_lap']:.3f} kg/lap")
    with fc5:
        st.metric("SAFETY RESERVE", f"{summary['fuel_safety_margin_kg']:.2f} kg", delta=summary["fuel_reserve_status"])

    st.markdown("---")

    # 3. SECTION 3: 4-CORNER WHEEL TIRE WEAR BREAKDOWN
    st.subheader("4-Corner Wheel Tire Wear Breakdown")
    tc1, tc2, tc3, tc4, tc5 = st.columns(5)
    with tc1:
        st.metric("FL WEAR (Front Left)", f"{summary['fl_final_wear']:.2f} %")
    with tc2:
        st.metric("FR WEAR (Front Right)", f"{summary['fr_final_wear']:.2f} %")
    with tc3:
        st.metric("RL WEAR (Rear Left)", f"{summary['rl_final_wear']:.2f} %")
    with tc4:
        st.metric("RR WEAR (Rear Right)", f"{summary['rr_final_wear']:.2f} %")
    with tc5:
        st.metric("PEAK WHEEL WEAR", f"{summary['max_corner_wear_pct']:.2f} %", delta=f"Wheel: {summary['most_worn_wheel']}")

    # Corner wear progression line chart if corner data exists
    c_df = analytics["corner_wear_df"]
    if not c_df.empty:
        st.markdown("**Lap-by-Lap 4-Corner Tire Wear Progression**")
        render_corner_chart = c_df.set_index("lap_number")[["tire_wear_fl", "tire_wear_fr", "tire_wear_rl", "tire_wear_rr"]]
        render_corner_chart.columns = ["FL Wear (%)", "FR Wear (%)", "RL Wear (%)", "RR Wear (%)"]
        st.line_chart(render_corner_chart)

    st.markdown("---")

    # 4. SECTION 4: AXLE & LATERAL WEAR BALANCE
    st.subheader("Axle & Lateral Degradation Balance")
    bal = analytics["balance"]
    bc1, bc2, bc3, bc4 = st.columns(4)
    with bc1:
        st.metric("FRONT AXLE AVG WEAR", f"{bal['front_avg_wear']:.2f} %")
    with bc2:
        st.metric("REAR AXLE AVG WEAR", f"{bal['rear_avg_wear']:.2f} %")
    with bc3:
        st.metric("FRONT/REAR BIAS DELTA", f"{bal['front_rear_delta']:+.2f} %", delta="Front-Heavy" if bal['front_rear_delta'] > 0 else "Rear-Heavy")
    with bc4:
        st.metric("LEFT/RIGHT BIAS DELTA", f"{bal['left_right_delta']:+.2f} %", delta="Left-Heavy" if bal['left_right_delta'] > 0 else "Right-Heavy")

    st.markdown("---")

    # 5. SECTION 5 & 6: STINT DEGRADATION & ESTIMATED REMAINING TIRE LIFE
    st.subheader("📊 Stint Degradation Rates & Estimated Remaining Tire Life")
    stint_analytics_df = analytics["stint_analytics_df"]

    if not stint_analytics_df.empty:
        display_stint_analytics = stint_analytics_df[[
            "stint_number",
            "compound",
            "start_lap",
            "end_lap",
            "stint_laps",
            "starting_wear",
            "ending_wear",
            "wear_delta",
            "degradation_pct_per_lap",
            "remaining_laps_display",
        ]].copy()

        display_stint_analytics["starting_wear"] = display_stint_analytics["starting_wear"].map("{:.2f}%".format)
        display_stint_analytics["ending_wear"] = display_stint_analytics["ending_wear"].map("{:.2f}%".format)
        display_stint_analytics["wear_delta"] = display_stint_analytics["wear_delta"].map("{:.2f}%".format)
        display_stint_analytics["degradation_pct_per_lap"] = display_stint_analytics["degradation_pct_per_lap"].map("{:.3f}% / lap".format)

        display_stint_analytics.columns = [
            "Stint",
            "Compound",
            "Start Lap",
            "End Lap",
            "Stint Laps",
            "Start Wear",
            "End Wear",
            "Wear Delta",
            "Degradation Rate",
            "Est. Remaining Tire Life (to 85%)",
        ]

        st.dataframe(display_stint_analytics, use_container_width=True, hide_index=True)
        st.caption("⚠️ Note: Estimated Remaining Tire Life is a read-only linear projection based on observed stint degradation rate to the 85% limit.")

    return scen_id


def prepare_strategy_details_view_data(
    adapter: StrategyDashboardAdapter,
    scenario_id: Optional[str] = None,
    lap_range: Optional[Tuple[int, int]] = None,
) -> Dict[str, Any]:
    """
    Prepares pure presentation view-data for Strategy Details & Validation Audit (G.4.6.6).
    Operates on a SINGLE selected strategy, extracting authoritative G.4.5.4 constraint validation
    violations, soft warnings, race session parameters, simulation assumptions, and interactive
    lap-by-lap execution audit trace telemetry without modifying domain objects.

    Args:
        adapter: StrategyDashboardAdapter instance.
        scenario_id: Canonical scenario ID. Defaults to leader if None.
        lap_range: Optional 1-based lap range tuple (start_lap, end_lap) to filter lap trace.

    Returns:
        Dict containing validation metrics, identity, race config, assumptions, and lap trace DataFrame.
    """
    if adapter is None:
        raise ValueError("adapter cannot be None")

    ranking_res: RankingResult = adapter.ranking_result
    if ranking_res.is_empty:
        return {
            "validation": {},
            "identity": {},
            "race_config": {},
            "assumptions": [],
            "lap_trace": {"lap_df": pd.DataFrame()},
            "is_empty": True,
            "scenario_id": None,
        }

    all_ranked_ids = [s.scenario_id for s in ranking_res.ranked_strategies]

    if scenario_id is None:
        scenario_id = ranking_res.leader_scenario_id or all_ranked_ids[0]

    if scenario_id not in adapter._ranked_map:
        return {
            "validation": {},
            "identity": {},
            "race_config": {},
            "assumptions": [],
            "lap_trace": {"lap_df": pd.DataFrame()},
            "is_empty": True,
            "error": f"Scenario ID '{scenario_id}' not found in ranking result",
            "scenario_id": scenario_id,
        }

    # 1. STRATEGY IDENTITY
    strat = adapter._ranked_map[scenario_id]
    scen = adapter._scenarios.get(scenario_id)

    generation_method = getattr(scen, "generation_method", "BOUNDED_GRID") if scen else "BOUNDED_GRID"
    starting_compound = getattr(scen, "starting_compound", "UNKNOWN") if scen else "UNKNOWN"
    compound_sequence = list(getattr(scen, "compound_sequence", [])) if scen else []
    
    stint_df = pd.DataFrame()
    try:
        stint_df = adapter.stint_dataframe(scenario_id)
        if not compound_sequence and not stint_df.empty and "compound" in stint_df.columns:
            compound_sequence = list(stint_df["compound"])
        if starting_compound == "UNKNOWN" and compound_sequence:
            starting_compound = compound_sequence[0]
    except (ValueError, KeyError, AttributeError):
        pass

    identity = {
        "rank": strat.rank,
        "scenario_id": strat.scenario_id,
        "canonical_key": strat.canonical_key,
        "total_race_time_sec": strat.total_race_time_sec,
        "delta_to_leader_sec": strat.delta_to_leader_sec,
        "pit_stop_count": strat.pit_stop_count,
        "final_fuel_kg": strat.final_fuel_kg,
        "avg_final_tire_wear_pct": strat.avg_final_tire_wear_pct,
        "warning_count": strat.warning_count,
        "generation_method": generation_method,
        "starting_compound": starting_compound,
        "compound_sequence": compound_sequence,
        "stint_count": len(compound_sequence) if compound_sequence else strat.pit_stop_count + 1,
    }

    # 2. VALIDATION & CONSTRAINT AUDIT
    val_res: Optional[ValidationResult] = adapter._val_results.get(scenario_id)
    val_df = pd.DataFrame()
    try:
        val_df = adapter.validation_dataframe(scenario_id)
    except (ValueError, KeyError, AttributeError):
        pass

    valid = True
    severity = "NONE"
    checked_count = 8
    validator_version = "1.0.0"
    violations_list = []
    warnings_list = []

    if val_res is not None:
        valid = val_res.valid
        severity = val_res.severity
        checked_count = val_res.checked_constraints_count
        validator_version = val_res.validator_version
        violations_list = [v.to_dict() for v in val_res.violations]
        warnings_list = list(val_res.warnings)
    elif not val_df.empty:
        valid = bool(val_df.iloc[0].get("valid", True))
        severity = str(val_df.iloc[0].get("severity", "NONE"))
        if "constraint_id" in val_df.columns:
            violations_list = val_df.to_dict(orient="records")
        if "warnings" in val_df.columns and val_df.iloc[0].get("warnings") != "None":
            w_str = str(val_df.iloc[0].get("warnings"))
            warnings_list = [w.strip() for w in w_str.split(",") if w.strip()]

    violation_count = len(violations_list)
    warning_count = len(warnings_list) if warnings_list else strat.warning_count

    # Category compliance breakdown
    categories = ["FUEL", "TIRE", "STINT", "PIT_STOP", "COMPOUND", "DISTANCE", "LAP", "CONSISTENCY"]
    category_breakdown = {cat: {"violations": 0, "warnings": 0} for cat in categories}
    for v in violations_list:
        cat = str(v.get("category", "CONSISTENCY")).upper()
        if cat not in category_breakdown:
            category_breakdown[cat] = {"violations": 0, "warnings": 0}
        category_breakdown[cat]["violations"] += 1

    validation_data = {
        "valid": valid,
        "severity": severity,
        "violation_count": violation_count,
        "warning_count": warning_count,
        "checked_constraints_count": checked_count,
        "validator_version": validator_version,
        "violations": violations_list,
        "warnings": warnings_list,
        "category_breakdown": category_breakdown,
        "violations_df": pd.DataFrame(violations_list) if violations_list else pd.DataFrame(),
    }

    # 3. RACE CONFIGURATION
    sim_res = adapter._sim_results.get(scenario_id)
    race_id = "RACE_DEFAULT"
    total_laps = DEFAULT_TOTAL_LAPS
    starting_fuel = DEFAULT_STARTING_FUEL_KG
    initial_compound = starting_compound
    pit_stop_loss_sec = DEFAULT_PIT_STOP_LOSS_SEC
    max_tire_wear = DEFAULT_MAX_TIRE_WEAR_PCT
    min_stint_laps = DEFAULT_MIN_STINT_LAPS

    if scen is not None:
        race_id = getattr(scen, "race_id", race_id)
        total_laps = getattr(scen, "total_laps", total_laps)
        if hasattr(scen, "stints") and scen.stints and hasattr(scen.stints[0], "starting_fuel"):
            starting_fuel = float(scen.stints[0].starting_fuel)
    if sim_res is not None:
        if hasattr(sim_res, "race_id"):
            race_id = getattr(sim_res, "race_id", race_id)
        if hasattr(sim_res, "starting_fuel") and sim_res.starting_fuel is not None:
            starting_fuel = float(sim_res.starting_fuel)
    if not stint_df.empty and "starting_fuel" in stint_df.columns:
        starting_fuel = float(stint_df["starting_fuel"].iloc[0])

    race_config_data = {
        "race_id": race_id,
        "total_laps": total_laps,
        "starting_fuel": starting_fuel,
        "initial_compound": initial_compound,
        "pit_stop_loss_sec": pit_stop_loss_sec,
        "max_tire_wear": max_tire_wear,
        "min_stint_laps": min_stint_laps,
    }

    # 4. SIMULATION ASSUMPTIONS
    assumptions_data = [
        {
            "parameter": "Pit Stop Time Loss Penalty",
            "value": f"{pit_stop_loss_sec:.2f} s",
            "type": "PROJECT SIMULATION ASSUMPTION",
            "description": "Stationary time + pit lane entry/exit delta time penalty incurred per pit stop.",
        },
        {
            "parameter": "Max Allowable Tire Wear Limit",
            "value": f"{max_tire_wear:.1f} %",
            "type": "PROJECT SIMULATION ASSUMPTION",
            "description": "Maximum physical tire degradation threshold allowed before triggering mandatory pit stop.",
        },
        {
            "parameter": "Minimum Stint Length",
            "value": f"{min_stint_laps} Laps",
            "type": "PROJECT SIMULATION ASSUMPTION",
            "description": "Minimum required stint duration in laps to prevent unrealistic short stints.",
        },
        {
            "parameter": "Minimum Fuel Reserve Baseline",
            "value": f"{DEFAULT_FIA_FUEL_RESERVE_KG:.2f} kg",
            "type": "FIA REGULATION",
            "description": "Mandatory minimum fuel sample required in fuel tank at race completion per FIA Technical Regulations.",
        },
        {
            "parameter": "Dry Compound Diversity Requirement",
            "value": "Mandatory Multi-Compound",
            "type": "FIA REGULATION",
            "description": "Driver must use at least two distinct dry tire compound specifications during a dry race session.",
        },
    ]

    # 5. INTERACTIVE LAP-BY-LAP EXECUTION AUDIT TRACE
    lap_df = pd.DataFrame()
    try:
        lap_df = adapter.lap_dataframe(scenario_id)
    except (ValueError, KeyError, AttributeError):
        pass

    fastest_lap_sec = float(lap_df["lap_time_sec"].min()) if not lap_df.empty and "lap_time_sec" in lap_df.columns else None
    avg_lap_sec = float(lap_df["lap_time_sec"].mean()) if not lap_df.empty and "lap_time_sec" in lap_df.columns else None
    total_pit_loss_sec = float(lap_df["pit_loss_sec"].sum()) if not lap_df.empty and "pit_loss_sec" in lap_df.columns else 0.0
    pit_laps = []
    if not lap_df.empty and "pit_loss_sec" in lap_df.columns and "lap_number" in lap_df.columns:
        pit_laps = [int(l) for l in lap_df[lap_df["pit_loss_sec"] > 0]["lap_number"]]

    filtered_lap_df = lap_df.copy()
    if lap_range and not filtered_lap_df.empty and "lap_number" in filtered_lap_df.columns:
        start_l, end_l = lap_range
        filtered_lap_df = filtered_lap_df[
            (filtered_lap_df["lap_number"] >= start_l) & (filtered_lap_df["lap_number"] <= end_l)
        ].copy()

    lap_trace_data = {
        "total_laps": len(lap_df) if not lap_df.empty else total_laps,
        "fastest_lap_sec": fastest_lap_sec,
        "avg_lap_sec": avg_lap_sec,
        "total_pit_loss_sec": total_pit_loss_sec,
        "pit_laps": pit_laps,
        "lap_df": filtered_lap_df,
        "raw_lap_df": lap_df,
    }

    return {
        "scenario_id": scenario_id,
        "is_empty": False,
        "identity": identity,
        "validation": validation_data,
        "race_config": race_config_data,
        "assumptions": assumptions_data,
        "lap_trace": lap_trace_data,
    }


def render_strategy_details(
    adapter: StrategyDashboardAdapter,
    scenario_id: Optional[str] = None,
) -> Optional[str]:
    """
    Renders the Strategy Details & Validation Audit UI component (G.4.6.6).
    Provides deep engineering transparency into G.4.5.4 constraint validation status,
    violations, soft warnings, race session parameters, simulation assumptions,
    and an interactive lap-by-lap execution audit trace table for the selected strategy.

    Args:
        adapter: StrategyDashboardAdapter instance.
        scenario_id: Optional strategy canonical scenario ID.

    Returns:
        Optional scenario_id rendered.
    """
    st.markdown("## STRATEGY VALIDATION & AUDIT")

    if adapter is None or adapter.ranking_result.is_empty:
        st.info("No strategy details available.")
        return None

    all_ranked_ids = [s.scenario_id for s in adapter.ranking_result.ranked_strategies]
    if scenario_id is None:
        scenario_id = st.session_state.get("selected_scenario_id", adapter.ranking_result.leader_scenario_id or all_ranked_ids[0])

    view_data = prepare_strategy_details_view_data(adapter, scenario_id=scenario_id)

    if view_data.get("is_empty"):
        if "error" in view_data:
            st.error(f"{view_data['error']}")
        else:
            st.warning("Selected strategy details unavailable.")
        return None

    scen_id = view_data["scenario_id"]
    identity = view_data["identity"]
    val = view_data["validation"]
    config = view_data["race_config"]
    assumptions = view_data["assumptions"]
    trace = view_data["lap_trace"]

    st.markdown(f"**Target Strategy:** `{scen_id}` | **Rank:** #{identity['rank']} | **Canonical Sequence:** `{identity['canonical_key']}`")

    # 1. SECTION 1: VALIDATION & CONSTRAINT AUDIT PANEL
    st.subheader("Validation & Constraint Audit")
    
    val_c1, val_c2, val_c3, val_c4 = st.columns(4)
    with val_c1:
        if val["valid"]:
            st.success("VALID STRATEGY")
        else:
            st.error("INVALID STRATEGY")
    with val_c2:
        sev_color = "green" if val["severity"] == "NONE" else ("orange" if val["severity"] == "WARNING" else "red")
        st.metric("SEVERITY LEVEL", val["severity"])
    with val_c3:
        st.metric("HARD VIOLATIONS", f"{val['violation_count']}")
    with val_c4:
        st.metric("SOFT WARNINGS", f"{val['warning_count']}")

    # Hard Violations Table
    if val["violation_count"] > 0:
        st.markdown("**🚨 Hard Constraint Violations (G.4.5.4)**")
        v_df = val["violations_df"]
        if not v_df.empty:
            display_v = v_df[[c for c in ["constraint_id", "category", "severity", "lap_number", "stint_id", "message", "actual_value", "expected_value"] if c in v_df.columns]].copy()
            display_v.columns = [c.replace("_", " ").title() for c in display_v.columns]
            st.dataframe(display_v, use_container_width=True, hide_index=True)
    else:
        st.caption("✅ No hard constraint violations detected by G.4.5.4 Constraint Validator.")

    # Soft Warnings List
    if val["warnings"]:
        st.markdown("**⚠️ Soft Warnings & Alerts**")
        for w in val["warnings"]:
            st.warning(f"• {w}")

    st.markdown("---")

    # 2. SECTION 2: STRATEGY IDENTITY & RACE CONFIG INSPECTOR
    st.subheader("📋 Strategy Identity & Session Parameters")
    
    ic1, ic2, ic3, ic4, ic5, ic6 = st.columns(6)
    with ic1:
        st.metric("TOTAL LAPS", f"{config['total_laps']} Laps")
    with ic2:
        st.metric("STARTING FUEL", f"{config['starting_fuel']:.1f} kg")
    with ic3:
        st.metric("INIT COMPOUND", identity["starting_compound"])
    with ic4:
        st.metric("PIT LOSS DELTA", f"{config['pit_stop_loss_sec']:.2f} s")
    with ic5:
        st.metric("MAX WEAR LIMIT", f"{config['max_tire_wear']:.1f} %")
    with ic6:
        st.metric("MIN STINT LENGTH", f"{config['min_stint_laps']} Laps")

    st.markdown("---")

    # 3. SECTION 3: SIMULATION ASSUMPTIONS AUDIT
    st.subheader("⚙️ Authoritative Simulation Assumptions Audit")
    assump_df = pd.DataFrame(assumptions)
    assump_df.columns = ["Parameter", "Configured Value", "Rule Classification", "Description"]
    st.dataframe(assump_df, use_container_width=True, hide_index=True)

    st.markdown("---")

    # 4. SECTION 4: INTERACTIVE LAP-BY-LAP EXECUTION AUDIT TRACE
    st.subheader("⏱️ Lap-by-Lap Execution Audit Trace")
    
    lap_df = trace["raw_lap_df"]
    if not lap_df.empty:
        max_laps = trace["total_laps"]
        
        tc_col1, tc_col2 = st.columns([2, 1])
        with tc_col1:
            selected_laps = st.slider(
                "Filter Lap Range for Audit:",
                min_value=1,
                max_value=max_laps,
                value=(1, max_laps),
                key="strategy_details_lap_slider",
            )
        with tc_col2:
            highlight_pits = st.checkbox("Highlight Pit Laps Only", value=False, key="strategy_details_pit_checkbox")

        # Filter by slider range
        render_trace_df = lap_df[
            (lap_df["lap_number"] >= selected_laps[0]) & (lap_df["lap_number"] <= selected_laps[1])
        ].copy()

        if highlight_pits and "pit_loss_sec" in render_trace_df.columns:
            render_trace_df = render_trace_df[render_trace_df["pit_loss_sec"] > 0].copy()

        if render_trace_df.empty:
            st.info("ℹ️ No laps match the selected lap trace filters.")
        else:
            display_trace = render_trace_df.copy()
            if "fuel_kg" in display_trace.columns:
                display_trace["fuel_kg"] = display_trace["fuel_kg"].map("{:.2f}".format)
            if "avg_tire_wear" in display_trace.columns:
                display_trace["avg_tire_wear"] = display_trace["avg_tire_wear"].map("{:.2f}%".format)
            if "lap_time_sec" in display_trace.columns:
                display_trace["lap_time_sec"] = display_trace["lap_time_sec"].map("{:.3f}".format)
            if "pit_loss_sec" in display_trace.columns:
                display_trace["pit_loss_sec"] = display_trace["pit_loss_sec"].map("{:.2f}".format)
            if "cum_time_sec" in display_trace.columns:
                display_trace["cum_time_sec"] = display_trace["cum_time_sec"].map("{:.3f}".format)

            st.dataframe(display_trace, use_container_width=True, hide_index=True)
            st.caption(f"Showing {len(render_trace_df)} of {max_laps} race laps for Strategy `{scen_id}`.")
    else:
        st.info("ℹ️ Lap-by-lap telemetry records unavailable for this strategy.")

    return scen_id


def render_strategy_dashboard_tab(adapter: StrategyDashboardAdapter):
    """
    Renders the complete Strategy Analytics Dashboard tab containing
    Leaderboard (G.4.6.2), Stint Timeline (G.4.6.4), Comparison (G.4.6.3),
    Fuel & 4-Corner Tire Analytics (G.4.6.5), and Strategy Details & Validation Audit (G.4.6.6).
    """
    if adapter is None or adapter.ranking_result.is_empty:
        st.info("ℹ️ No strategy data available.")
        return

    # 1. Render Leaderboard
    selected_id = render_strategy_leaderboard(adapter)

    st.markdown("<br><hr><br>", unsafe_allow_html=True)

    # 2. Render Stint Timeline for Selected Strategy
    render_stint_timeline(adapter, scenario_id=selected_id)

    st.markdown("<br><hr><br>", unsafe_allow_html=True)

    # 3. Render Fuel & 4-Corner Tire Telemetry Analytics for Selected Strategy
    render_fuel_tire_analytics(adapter, scenario_id=selected_id)

    st.markdown("<br><hr><br>", unsafe_allow_html=True)

    # 4. Render Strategy Details & Validation Audit Cockpit for Selected Strategy
    render_strategy_details(adapter, scenario_id=selected_id)

    st.markdown("<br><hr><br>", unsafe_allow_html=True)

    # 5. Render Multi-Strategy Comparison
    default_ids = []
    leader_id = adapter.ranking_result.leader_scenario_id
    if leader_id:
        default_ids.append(leader_id)
    if selected_id and selected_id not in default_ids:
        default_ids.append(selected_id)

    render_strategy_comparison(adapter, default_selected_ids=default_ids)

