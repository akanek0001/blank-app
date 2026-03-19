from __future__ import annotations

from typing import Any, Optional

import pandas as pd
import streamlit as st

from config import AppConfig
from core.auth import AdminAuth
from core.utils import U
from engine.finance_engine import FinanceEngine
from repository.repository import Repository
from store.datastore import DataStore


class DashboardPage:
    """
    ダッシュボード表示専用ページ。
    - 集計表示に集中
    - DataFrame は Arrow エラー回避のため安全表示
    """

    def __init__(self, repo: Repository, engine: FinanceEngine, store: DataStore):
        self.repo = repo
        self.engine = engine
        self.store = store

    # =========================================================
    # Safe table
    # =========================================================
    @staticmethod
    def _to_safe_cell(value: Any) -> str:
        if value is None:
            return ""
        try:
            if pd.isna(value):
                return ""
        except Exception:
            pass
        try:
            return str(value)
        except Exception:
            return ""

    @classmethod
    def _safe_df(cls, df: Optional[pd.DataFrame]) -> pd.DataFrame:
        if df is None:
            return pd.DataFrame()

        out = df.copy()
        out = out.drop(columns=["_row_id"], errors="ignore")
        out = out.reset_index(drop=True)
        out.columns = [cls._to_safe_cell(c) for c in out.columns]

        for col in out.columns:
            out[col] = out[col].map(cls._to_safe_cell)

        return out

    @classmethod
    def _render_html_table(cls, df: pd.DataFrame) -> None:
        safe_df = cls._safe_df(df)

        if safe_df.empty:
            st.info("表示データがありません。")
            return

        html_table = safe_df.to_html(index=False, escape=True)

        st.markdown(
            """
            <style>
            .dashboard-table-wrap {
                overflow-x: auto;
                border: 1px solid #ddd;
                border-radius: 8px;
                background: white;
                padding: 8px;
            }
            .dashboard-table-wrap table {
                border-collapse: collapse;
                width: 100%;
                font-size: 13px;
            }
            .dashboard-table-wrap th, .dashboard-table-wrap td {
                border: 1px solid #ddd;
                padding: 6px 8px;
                text-align: left;
                vertical-align: top;
                white-space: nowrap;
            }
            .dashboard-table-wrap th {
                background: #f7f7f7;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )

        st.markdown(
            f'<div class="dashboard-table-wrap">{html_table}</div>',
            unsafe_allow_html=True,
        )

    # =========================================================
    # Summary helpers
    # =========================================================
    @staticmethod
    def _sum_principal(members_df: pd.DataFrame) -> float:
        if members_df is None or members_df.empty:
            return 0.0
        df = members_df.copy()
        if "IsActive" in df.columns:
            df = df[df["IsActive"] == True]
        if "Principal" not in df.columns:
            return 0.0
        try:
            return float(pd.to_numeric(df["Principal"], errors="coerce").fillna(0).sum())
        except Exception:
            return 0.0

    @staticmethod
    def _count_active_members(members_df: pd.DataFrame) -> int:
        if members_df is None or members_df.empty:
            return 0
        df = members_df.copy()
        if "IsActive" in df.columns:
            df = df[df["IsActive"] == True]
        return int(len(df))

    @staticmethod
    def _count_active_projects(settings_df: pd.DataFrame) -> int:
        if settings_df is None or settings_df.empty:
            return 0
        df = settings_df.copy()
        if "Active" in df.columns:
            df = df[df["Active"] == True]
        if "Project_Name" not in df.columns:
            return 0
        return int(df["Project_Name"].astype(str).str.strip().replace("", pd.NA).dropna().nunique())

    @staticmethod
    def _today_apr_total(ledger_df: pd.DataFrame) -> float:
        if ledger_df is None or ledger_df.empty:
            return 0.0
        today = U.fmt_date(U.now_jst())
        df = ledger_df.copy()

        if "Datetime_JST" not in df.columns or "Type" not in df.columns or "Amount" not in df.columns:
            return 0.0

        df = df[
            (df["Datetime_JST"].astype(str).str.startswith(today))
            & (df["Type"].astype(str).str.strip() == AppConfig.TYPE["APR"])
        ].copy()

        try:
            return float(pd.to_numeric(df["Amount"], errors="coerce").fillna(0).sum())
        except Exception:
            return 0.0

    @staticmethod
    def _recent_ledger(ledger_df: pd.DataFrame, limit: int = 20) -> pd.DataFrame:
        if ledger_df is None or ledger_df.empty:
            return pd.DataFrame()

        df = ledger_df.copy()
        if "Datetime_JST" in df.columns:
            df = df.sort_values("Datetime_JST", ascending=False)
        return df.head(limit).reset_index(drop=True)

    @staticmethod
    def _project_summary(members_df: pd.DataFrame) -> pd.DataFrame:
        if members_df is None or members_df.empty:
            return pd.DataFrame()

        df = members_df.copy()
        if "IsActive" in df.columns:
            df = df[df["IsActive"] == True]

        if df.empty:
            return pd.DataFrame()

        if "Principal" in df.columns:
            df["Principal_num"] = pd.to_numeric(df["Principal"], errors="coerce").fillna(0.0)
        else:
            df["Principal_num"] = 0.0

        summary = (
            df.groupby("Project_Name", dropna=False)
            .agg(
                Members=("PersonName", "count"),
                Total_Principal=("Principal_num", "sum"),
            )
            .reset_index()
        )

        summary["Total_Principal"] = summary["Total_Principal"].map(lambda x: U.fmt_usd(float(x)))
        return summary

    # =========================================================
    # Render
    # =========================================================
    def render(
        self,
        settings_df: pd.DataFrame,
        members_df: pd.DataFrame,
        ledger_df: pd.DataFrame,
        apr_summary_df: pd.DataFrame,
    ) -> None:
        st.subheader("📊 ダッシュボード")
        st.caption(f"{AppConfig.RANK_LABEL} / 管理者: {AdminAuth.current_label()}")

        total_principal = self._sum_principal(members_df)
        active_members = self._count_active_members(members_df)
        active_projects = self._count_active_projects(settings_df)
        today_apr = self._today_apr_total(ledger_df)

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("有効プロジェクト数", str(active_projects))
        c2.metric("有効メンバー数", str(active_members))
        c3.metric("総元本", U.fmt_usd(total_principal))
        c4.metric("本日のAPR合計", U.fmt_usd(today_apr))

        st.markdown("#### プロジェクト別サマリー")
        self._render_html_table(self._project_summary(members_df))

        st.markdown("#### APRサマリー")
        self._render_html_table(apr_summary_df)

        st.markdown("#### 最新Ledger")
        self._render_html_table(self._recent_ledger(ledger_df, limit=20))
