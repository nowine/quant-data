"""Sector aggregation — group ETF snapshot by industry sector and rank.

This module takes a full-market ETF snapshot DataFrame and a sector mapping,
then produces sector-level aggregated statistics (avg change, total volume,
rise/fall counts) and a ranked table.
"""

from __future__ import annotations

import pandas as pd


def aggregate_by_sector(
    snapshot_df: pd.DataFrame,
    sector_mapping: dict[str, list[str]],
    *,
    code_col: str = "code",
    change_col: str = "change_pct",
    volume_col: str | None = None,
) -> pd.DataFrame:
    """Aggregate ETF snapshot data by industry sector.

    Args:
        snapshot_df: DataFrame with ETF-level data.
        sector_mapping: dict mapping sector name -> list of ETF codes.
        code_col: column name for ETF code in snapshot_df.
        change_col: column name for price change percentage in snapshot_df.
        volume_col: column name for volume in snapshot_df (optional).

    Returns:
        DataFrame with one row per sector, columns:
            - sector: sector name
            - avg_change_pct: average change % of ETFs in sector
            - total_volume: sum of volume (if volume_col provided)
            - rise_count: number of ETFs with positive change
            - fall_count: number of ETFs with negative change
            - total_count: total ETFs in sector
            - rise_ratio: rise_count / total_count
    """
    rows = []
    for sector, codes in sector_mapping.items():
        subset = snapshot_df[snapshot_df[code_col].isin(codes)]
        if subset.empty:
            continue
        total_count = len(subset)
        rise_count = int((subset[change_col] > 0).sum())
        fall_count = int((subset[change_col] < 0).sum())
        avg_change_pct = float(subset[change_col].mean())
        total_volume = float(subset[volume_col].sum() if volume_col and volume_col in subset.columns else 0)
        rows.append(
            {
                "sector": sector,
                "avg_change_pct": round(avg_change_pct, 3),
                "total_volume": round(total_volume, 2),
                "rise_count": rise_count,
                "fall_count": fall_count,
                "total_count": total_count,
                "rise_ratio": round(rise_count / total_count, 3) if total_count else 0,
            }
        )
    return pd.DataFrame(rows)


def rank_sectors(sector_df: pd.DataFrame) -> pd.DataFrame:
    """Rank sectors by avg_change_pct descending.

    Args:
        sector_df: output of aggregate_by_sector()

    Returns:
        DataFrame sorted by avg_change_pct desc, with added rank column (1=best)
    """
    df = sector_df.sort_values("avg_change_pct", ascending=False).reset_index(drop=True)
    df.insert(0, "rank", range(1, len(df) + 1))
    return df