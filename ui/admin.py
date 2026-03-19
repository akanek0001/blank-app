from __future__ import annotations

from typing import Optional, Any

import html
import pandas as pd
import streamlit as st

from repository.repository import Repository
from store.datastore import DataStore


class AdminPage:
    def __init__(self, repo: Repository, store: DataStore):
        self.repo = repo
        self.store = store

    # =========================================================
    # Safe convert
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

        if isinstance(value, bytes):
            try:
                return value.decode("utf-8", errors="ignore")
            except Exception:
                return str(value)

        if isinstance(value, (list, tuple, set, dict)):
            return str(value)

        try:
            return str(value)
        except Exception:
            return ""

    @classmethod
    def _safe_df(cls, df: Optional[pd.DataFrame]) -> pd.DataFrame:
        if df is None:
            return pd.DataFrame()

        try:
            out = df.copy()
        except Exception:
            return pd.DataFrame()

        out = out.drop(columns=["_row_id"], errors="ignore")
        out = out.reset_index(drop=True)
        out.columns = [cls._to_safe_cell(c) for c in out.columns]

        for col in out.columns:
            out[col] = out[col].map(cls._to_safe_cell)

        return out

    @staticmethod
    def _download_csv_button(label: str, df: pd.DataFrame, file_name: str) -> None:
        csv_data = df.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            label=label,
            data=csv_data,
            file_name=file_name,
            mime="text/csv",
            use_container_width=True,
        )

    @staticmethod
    def _render_html_table(df: pd.DataFrame) -> None:
        if df.empty:
            st.info("データがありません。")
            return

        html_table = df.to_html(index=False, escape=True)
        st.markdown(
            """
            <style>
            .admin-table-wrap {
                overflow-x: auto;
                border: 1px solid #ddd;
                border-radius: 8px;
                background: white;
                padding: 8px;
            }
            .admin-table-wrap table {
                border-collapse: collapse;
                width: 100%;
                font-size: 13px;
            }
            .admin-table-wrap th, .admin-table-wrap td {
                border: 1px solid #ddd;
                padding: 6px 8px;
                text-align: left;
                vertical-align: top;
                white-space: nowrap;
            }
            .admin-table-wrap th {
                background: #f7f7f7;
                position: sticky;
                top: 0;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(f'<div class="admin-table-wrap">{html_table}</div>', unsafe_allow_html=True)

    def _render_table_block(self, title: str, df: Optional[pd.DataFrame], file_name: str) -> None:
        st.markdown(f"#### {html.escape(title)}")

        safe_df = self._safe_df(df)

        if safe_df.empty:
            st.info(f"{title} は空です。")
            return

        c1, c2 = st.columns([3, 1])
        with c1:
            st.caption(f"件数: {len(safe_df)}")
        with c2:
            self._download_csv_button(f"{title} をCSV出力", safe_df, file_name)

        self._render_html_table(safe_df)

    # =========================================================
    # Main
    # =========================================================
    def render(
        self,
        settings_df: Optional[pd.DataFrame],
        members_df: Optional[pd.DataFrame],
        line_users_df: Optional[pd.DataFrame],
    ) -> None:
        st.subheader("🛠 管理ページ")

        safe_settings = self._safe_df(settings_df)
        safe_members = self._safe_df(members_df)
        safe_line_users = self._safe_df(line_users_df)

        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Settings 件数", len(safe_settings))
        with c2:
            st.metric("Members 件数", len(safe_members))
        with c3:
            st.metric("LineUsers 件数", len(safe_line_users))

        tab1, tab2, tab3 = st.tabs(["Settings", "Members", "LineUsers"])

        with tab1:
            self._render_table_block("Settings 一覧", safe_settings, "settings_export.csv")

        with tab2:
            self._render_table_block("Members 一覧", safe_members, "members_export.csv")

        with tab3:
            self._render_table_block("LineUsers 一覧", safe_line_users, "lineusers_export.csv")
