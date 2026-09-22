"""Tests for sector_aggregator module."""

import pandas as pd
import pytest

from src.sector_aggregator import aggregate_by_sector, rank_sectors


@pytest.fixture
def snapshot_df():
    """Mock ETF snapshot matching akshare fund_etf_category_sina output."""
    return pd.DataFrame(
        [
            # 宽基
            {"代码": "510300", "涨跌幅": 1.5, "成交额": 1_000_000},
            {"代码": "510500", "涨跌幅": 2.0, "成交额": 800_000},
            # 半导体/芯片
            {"代码": "512480", "涨跌幅": -1.0, "成交额": 500_000},
            {"代码": "588750", "涨跌幅": 3.0, "成交额": 600_000},
            # 黄金
            {"代码": "518880", "涨跌幅": 0.5, "成交额": 2_000_000},
            {"代码": "159934", "涨跌幅": 0.8, "成交额": 1_500_000},
            # 机器人
            {"代码": "159530", "涨跌幅": 5.0, "成交额": 300_000},
        ]
    )


@pytest.fixture
def sector_mapping():
    return {
        "宽基": ["510300", "510500"],
        "半导体/芯片": ["512480", "588750"],
        "黄金": ["518880", "159934"],
        "机器人": ["159530"],
    }


class TestAggregateBySector:
    def test_aggregates_correct_avg_change(self, snapshot_df, sector_mapping):
        result = aggregate_by_sector(snapshot_df, sector_mapping, code_col="代码", change_col="涨跌幅", volume_col="成交额")
        row = result[result["sector"] == "宽基"].iloc[0]
        assert row["avg_change_pct"] == pytest.approx(1.75, rel=0.01)  # (1.5+2.0)/2

    def test_aggregates_total_volume(self, snapshot_df, sector_mapping):
        result = aggregate_by_sector(snapshot_df, sector_mapping, code_col="代码", change_col="涨跌幅", volume_col="成交额")
        row = result[result["sector"] == "黄金"].iloc[0]
        assert row["total_volume"] == pytest.approx(3_500_000, rel=0.01)

    def test_counts_rise_fall(self, snapshot_df, sector_mapping):
        result = aggregate_by_sector(snapshot_df, sector_mapping, code_col="代码", change_col="涨跌幅", volume_col="成交额")
        chip = result[result["sector"] == "半导体/芯片"].iloc[0]
        assert chip["rise_count"] == 1
        assert chip["fall_count"] == 1

    def test_robotsector_rise_ratio(self, snapshot_df, sector_mapping):
        result = aggregate_by_sector(snapshot_df, sector_mapping, code_col="代码", change_col="涨跌幅", volume_col="成交额")
        row = result[result["sector"] == "机器人"].iloc[0]
        assert row["rise_count"] == 1
        assert row["fall_count"] == 0
        assert row["total_count"] == 1
        assert row["rise_ratio"] == 1.0

    def test_skips_empty_sector(self, snapshot_df, sector_mapping):
        result = aggregate_by_sector(snapshot_df, sector_mapping, code_col="代码", change_col="涨跌幅", volume_col="成交额")
        assert "军工" not in result["sector"].values

    def test_unknown_codes_in_snapshot_ignored(self, snapshot_df, sector_mapping):
        # snapshot has extra code not in mapping
        extra = snapshot_df.copy()
        extra.loc[len(extra)] = {"代码": "999999", "涨跌幅": 99.0, "成交额": 1}
        result = aggregate_by_sector(extra, sector_mapping, code_col="代码", change_col="涨跌幅", volume_col="成交额")
        assert "999999" not in result["sector"].values  # no error, no sector


class TestRankSectors:
    def test_rank_sorted_by_avg_change_desc(self, snapshot_df, sector_mapping):
        agg = aggregate_by_sector(snapshot_df, sector_mapping, code_col="代码", change_col="涨跌幅", volume_col="成交额")
        ranked = rank_sectors(agg)
        assert ranked.iloc[0]["sector"] == "机器人"  # 5.0%
        assert ranked.iloc[0]["rank"] == 1
        # 黄金 avg=(0.5+0.8)/2=0.65%, 半导体/芯片=-1.0% → 黄金 is last

    def test_rank_contiguous(self, snapshot_df, sector_mapping):
        agg = aggregate_by_sector(snapshot_df, sector_mapping, code_col="代码", change_col="涨跌幅", volume_col="成交额")
        ranked = rank_sectors(agg)
        assert list(ranked["rank"]) == list(range(1, len(ranked) + 1))