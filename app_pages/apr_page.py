from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import pandas as pd
import streamlit as st

from config import AppConfig
from core.auth import AdminAuth
from core.utils import U
from engine.finance_engine import FinanceEngine
from repository.repository import Repository
from services.ocr_processor import OCRProcessor
from services.transaction_manager import TransactionManager
from store.datastore import DataStore


class APRPage:
    """
    画面表示に集中する簡易版 APR ページ。
    Arrow / PyArrow 変換エラーを避けるため、表は HTML で表示する。
    """

    def __init__(self, repo: Repository, engine: FinanceEngine, store: DataStore):
        self.repo = repo
        self.engine = engine
        self.store = store
        self.tx_manager = TransactionManager(repo)

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
            .apr-table-wrap {
                overflow-x: auto;
                border: 1px solid #ddd;
                border-radius: 8px;
                background: white;
                padding: 8px;
            }
            .apr-table-wrap table {
                border-collapse: collapse;
                width: 100%;
                font-size: 13px;
            }
            .apr-table-wrap th, .apr-table-wrap td {
                border: 1px solid #ddd;
                padding: 6px 8px;
                text-align: left;
                vertical-align: top;
                white-space: nowrap;
            }
            .apr-table-wrap th {
                background: #f7f7f7;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )

        st.markdown(
            f'<div class="apr-table-wrap">{html_table}</div>',
            unsafe_allow_html=True,
        )

    # =========================================================
    # Input
    # =========================================================
    def _render_input_section(self):
        st.markdown("#### 流動性 / 昨日の収益 / APR（手動入力）")
        c1, c2, c3 = st.columns(3)

        with c1:
            total_liquidity_raw = st.text_input(
                "流動性",
                value=st.session_state.get("sv_total_liquidity", ""),
                key="sv_total_liquidity",
                placeholder="$78,354.35",
            )
        with c2:
            yesterday_profit_raw = st.text_input(
                "昨日の収益",
                value=st.session_state.get("sv_yesterday_profit", ""),
                key="sv_yesterday_profit",
                placeholder="$90.87",
            )
        with c3:
            apr_raw = st.text_input(
                "APR（%）",
                value=st.session_state.get("sv_apr", ""),
                key="sv_apr",
                placeholder="42.33",
            )

        return (
            U.to_f(total_liquidity_raw),
            U.to_f(yesterday_profit_raw),
            U.apr_val(apr_raw),
        )

    # =========================================================
    # Files
    # =========================================================
    def _get_default_watch_folder(self) -> str:
        try:
            return str(st.secrets.get("local_paths", {}).get("apr_watch_folder", "")).strip()
        except Exception:
            return ""

    def _folder_image_files(self, folder_path: str):
        path = Path(folder_path).expanduser()
        if not path.exists() or not path.is_dir():
            return []

        exts = {".png", ".jpg", ".jpeg", ".webp"}
        files = [p for p in path.iterdir() if p.is_file() and p.suffix.lower() in exts]
        files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return files

    # =========================================================
    # OCR
    # =========================================================
    def _render_ocr_tool(
        self,
        settings_df: pd.DataFrame,
        project: str,
        file_bytes: Optional[bytes],
    ):
        if not file_bytes:
            st.info("画像を選択すると OCR セクションが表示されます。")
            return

        platform = OCRProcessor.detect_platform(file_bytes)
        st.caption(f"現在のプラットフォーム判定: {platform}")

        try:
            boxes = OCRProcessor.get_smartvault_boxes(settings_df, project, platform)
            metrics = OCRProcessor.extract_metrics(file_bytes, boxes)
        except Exception as e:
            st.error(f"OCR設定エラー: {e}")
            return

        st.write(
            {
                "platform_detected": platform,
                "smartvault_boxes_in_use": {k: v.to_dict() for k, v in boxes.items()},
            }
        )

        st.image(metrics["preview"], caption=f"赤枠 = {platform} OCR対象範囲", width=500)

        c1, c2, c3 = st.columns(3)
        with c1:
            st.write("流動性", U.fmt_usd(metrics["total_liquidity"] or 0))
        with c2:
            st.write("昨日の収益", U.fmt_usd(metrics["yesterday_profit"] or 0))
        with c3:
            st.write(
                "APR",
                f"{float(metrics['apr_value']):.2f}%"
                if metrics["apr_value"] is not None
                else "未検出",
            )

    # =========================================================
    # Calculation Preview
    # =========================================================
    def _render_calculation_preview(
        self,
        settings_df: pd.DataFrame,
        members_df: pd.DataFrame,
        apr: float,
    ):
        projects = self.repo.active_projects(settings_df)
        if not projects:
            st.warning("有効（Active=TRUE）のプロジェクトがありません。")
            return

        project = projects[0]
        row = settings_df[settings_df["Project_Name"] == str(project)].iloc[0]
        project_net_factor = float(row.get("Net_Factor", AppConfig.FACTOR["MASTER"]))
        mem = self.repo.project_members_active(members_df, project)

        if mem.empty:
            st.info("対象メンバーがいません。")
            return

        preview_df = self.engine.calc_project_apr(mem, float(apr), project_net_factor, project)

        st.markdown("#### 計算プレビュー")
        self._render_html_table(preview_df)

    # =========================================================
    # Main
    # =========================================================
    def render(self, settings_df: pd.DataFrame, members_df: pd.DataFrame):
        st.subheader("📈 APR 確定")
        st.caption(f"{AppConfig.RANK_LABEL} / 管理者: {AdminAuth.current_label()}")

        projects = self.repo.active_projects(settings_df)
        if not projects:
            st.warning("有効（Active=TRUE）のプロジェクトがありません。")
            return

        project = st.selectbox("基準プロジェクト", projects)

        total_liquidity, yesterday_profit, apr = self._render_input_section()

        st.info(
            f"流動性 = {U.fmt_usd(total_liquidity)} / "
            f"昨日の収益 = {U.fmt_usd(yesterday_profit)} / "
            f"最終APR = {apr:.4f}%"
        )

        st.markdown("#### フォルダから画像取得")
        default_watch_folder = self._get_default_watch_folder()
        folder_path = st.text_input(
            "監視フォルダパス",
            value=default_watch_folder,
            key="apr_watch_folder",
            placeholder="/Users/yourname/Desktop/smartvault_images",
        )

        image_files = self._folder_image_files(folder_path) if folder_path else []
        selected_evidence_bytes = None

        if image_files:
            labels = [p.name for p in image_files]
            selected_label = st.selectbox(
                "フォルダ内画像",
                labels,
                index=0,
                key="apr_folder_file_select",
            )
            selected_file = image_files[labels.index(selected_label)]
            selected_evidence_bytes = selected_file.read_bytes()
            st.image(
                selected_evidence_bytes,
                caption=f"フォルダ画像プレビュー: {selected_file.name}",
                width=500,
            )

        uploaded = st.file_uploader(
            "手動アップロード",
            type=["png", "jpg", "jpeg"],
            key="apr_img",
        )
        if uploaded is not None:
            selected_evidence_bytes = uploaded.getvalue()

        self._render_ocr_tool(settings_df, project, selected_evidence_bytes)
        self._render_calculation_preview(settings_df, members_df, apr)

        st.caption("app_pages/apr_page.py を安全表示版に置換済み")
