from __future__ import annotations

from typing import Optional

import pandas as pd
import streamlit as st


class AdminPage:
    # =========================================================
    # Utils
    # =========================================================
    @staticmethod
    def _safe_df_for_streamlit(df: Optional[pd.DataFrame]) -> pd.DataFrame:
        if df is None:
            return pd.DataFrame()

        out = df.copy()

        # Streamlit / pyarrow で落ちやすい列を除外
        out = out.drop(columns=["_row_id"], errors="ignore")

        # None / NaN を空文字へ
        out = out.fillna("")

        # Arrow変換エラー回避のため全列文字列化
        for col in out.columns:
            try:
                out[col] = out[col].astype(str)
            except Exception:
                out[col] = out[col].map(lambda x: "" if x is None else str(x))

        return out

    @staticmethod
    def _download_csv_button(label: str, df: pd.DataFrame, file_name: str) -> None:
        safe_df = df.copy()
        csv_data = safe_df.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            label=label,
            data=csv_data,
            file_name=file_name,
            mime="text/csv",
            use_container_width=True,
        )

    def _render_table_block(self, title: str, df: Optional[pd.DataFrame], file_name: str) -> None:
        st.markdown(f"#### {title}")

        if df is None or df.empty:
            st.info(f"{title} は空です。")
            return

        safe_df = self._safe_df_for_streamlit(df)

        c1, c2 = st.columns([3, 1])
        with c1:
            st.caption(f"件数: {len(safe_df)}")
        with c2:
            self._download_csv_button(f"{title} をCSV出力", safe_df, file_name)

        st.dataframe(safe_df, use_container_width=True, hide_index=True)

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

        safe_settings = self._safe_df_for_streamlit(settings_df)
        safe_members = self._safe_df_for_streamlit(members_df)
        safe_line_users = self._safe_df_for_streamlit(line_users_df)

        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Settings 件数", len(safe_settings))
        with c2:
            st.metric("Members 件数", len(safe_members))
        with c3:
            st.metric("LineUsers 件数", len(safe_line_users))

        tab1, tab2, tab3 = st.tabs(
            [
                "Settings",
                "Members",
                "LineUsers",
            ]
        )

        with tab1:
            self._render_table_block("Settings 一覧", safe_settings, "settings_export.csv")

        with tab2:
            self._render_table_block("Members 一覧", safe_members, "members_export.csv")

        with tab3:
            self._render_table_block("LineUsers 一覧", safe_line_users, "lineusers_export.csv")
