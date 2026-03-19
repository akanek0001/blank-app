from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st

from config import AppConfig
from core.auth import AdminAuth
from core.utils import U
from engine.finance_engine import FinanceEngine
from repository.repository import Repository
from services.external_service import ExternalService
from services.ocr_processor import OCRProcessor
from store.datastore import DataStore


class APRPage:
    OCR_TX_HISTORY_SHEET = "OCR_Transaction_History"
    OCR_TX_HISTORY_HEADERS = [
        "Unique_Key",
        "Date_Label",
        "Time_Label",
        "Type_Label",
        "Amount_USD",
        "Token_Amount",
        "Token_Symbol",
        "Source_Image",
        "Source_Project",
        "OCR_Raw_Text",
        "CreatedAt_JST",
    ]

    def __init__(self, repo: Repository, engine: FinanceEngine, store: DataStore):
        self.repo = repo
        self.engine = engine
        self.store = store

    # =========================================================
    # Safe table render
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
    # File helpers
    # =========================================================
    def _folder_image_files(self, folder_path: str) -> List[Path]:
        path = Path(folder_path).expanduser()
        if not path.exists() or not path.is_dir():
            return []

        exts = {".png", ".jpg", ".jpeg", ".webp"}
        files = [p for p in path.iterdir() if p.is_file() and p.suffix.lower() in exts]
        files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return files

    def _get_default_watch_folder(self) -> str:
        try:
            return str(st.secrets.get("local_paths", {}).get("apr_watch_folder", "")).strip()
        except Exception:
            return ""

    # =========================================================
    # OCR: SmartVault main metrics
    # =========================================================
    def _apply_ocr_result(self, file_bytes: bytes, settings_df: pd.DataFrame, project: str) -> None:
        platform = OCRProcessor.detect_platform(file_bytes)

        crop_left_ratio, crop_top_ratio, crop_right_ratio, crop_bottom_ratio = (
            OCRProcessor.get_general_crop_ratios(settings_df, project, platform)
        )

        raw_text = ExternalService.ocr_space_extract_text_with_crop(
            file_bytes=file_bytes,
            crop_left_ratio=crop_left_ratio,
            crop_top_ratio=crop_top_ratio,
            crop_right_ratio=crop_right_ratio,
            crop_bottom_ratio=crop_bottom_ratio,
        )

        if raw_text:
            with st.expander("OCR生テキスト（通常範囲）", expanded=False):
                st.text(raw_text)

        st.info(
            f"OCR切り抜き範囲: left={crop_left_ratio:.3f}, top={crop_top_ratio:.3f}, "
            f"right={crop_right_ratio:.3f}, bottom={crop_bottom_ratio:.3f}"
        )

        boxes = OCRProcessor.get_smartvault_boxes(settings_df, project, platform)
        smart = OCRProcessor.extract_metrics(file_bytes, boxes)

        st.markdown(f"#### SmartVault OCR結果 ({platform})")
        st.image(smart["preview"], caption="赤枠 = OCR対象範囲", width=500)

        c_a, c_b, c_c = st.columns(3)
        with c_a:
            if smart["total_liquidity"] is not None:
                st.success(f"流動性: {U.fmt_usd(float(smart['total_liquidity']))}")
            else:
                st.warning("流動性: 未検出")
        with c_b:
            if smart["yesterday_profit"] is not None:
                st.success(f"昨日の収益: {U.fmt_usd(float(smart['yesterday_profit']))}")
            else:
                st.warning("昨日の収益: 未検出")
        with c_c:
            if smart["apr_value"] is not None:
                st.success(f"APR: {float(smart['apr_value']):.2f}%")
            else:
                st.warning("APR: 未検出")

        with st.expander("OCR生テキスト（流動性）", expanded=False):
            st.text(smart["total_text"] or "")
        with st.expander("OCR生テキスト（昨日の収益）", expanded=False):
            st.text(smart["profit_text"] or "")
        with st.expander("OCR生テキスト（APR）", expanded=False):
            st.text(smart["apr_text"] or "")

        if smart["total_liquidity"] is not None:
            st.session_state["sv_total_liquidity"] = f"{float(smart['total_liquidity']):,.2f}"
            st.session_state["ocr_total_liquidity"] = float(smart["total_liquidity"])
        if smart["yesterday_profit"] is not None:
            st.session_state["sv_yesterday_profit"] = f"{float(smart['yesterday_profit']):,.2f}"
            st.session_state["ocr_yesterday_profit"] = float(smart["yesterday_profit"])
        if smart["apr_value"] is not None:
            st.session_state["sv_apr"] = f"{float(smart['apr_value']):.4f}"
            st.session_state["ocr_apr"] = float(smart["apr_value"])

    # =========================================================
    # OCR history sheet
    # =========================================================
    def _ensure_ocr_tx_history_sheet(self) -> None:
        book = self.repo.gs.book
        try:
            ws = book.worksheet(self.OCR_TX_HISTORY_SHEET)
        except Exception:
            ws = book.add_worksheet(title=self.OCR_TX_HISTORY_SHEET, rows=5000, cols=20)
            ws.append_row(self.OCR_TX_HISTORY_HEADERS, value_input_option="USER_ENTERED")
            return

        try:
            first = ws.row_values(1)
        except Exception:
            return

        if not first:
            ws.append_row(self.OCR_TX_HISTORY_HEADERS, value_input_option="USER_ENTERED")
            return

        current = [str(c).strip() for c in first if str(c).strip()]
        missing = [h for h in self.OCR_TX_HISTORY_HEADERS if h not in current]
        if missing:
            ws.update("1:1", [current + missing])

    def _load_existing_ocr_tx_keys(self) -> set[str]:
        self._ensure_ocr_tx_history_sheet()
        try:
            ws = self.repo.gs.book.worksheet(self.OCR_TX_HISTORY_SHEET)
            values = ws.get_all_values()
        except Exception:
            return set()

        if not values or len(values) < 2:
            return set()

        headers = values[0]
        if "Unique_Key" not in headers:
            return set()

        key_idx = headers.index("Unique_Key")
        out: set[str] = set()

        for row in values[1:]:
            row = row + [""] * (len(headers) - len(row))
            key = str(row[key_idx]).strip()
            if key:
                out.add(key)

        return out

    def _append_ocr_tx_rows(self, rows: List[List[Any]]) -> None:
        if not rows:
            return

        self._ensure_ocr_tx_history_sheet()
        ws = self.repo.gs.book.worksheet(self.OCR_TX_HISTORY_SHEET)
        for row in rows:
            ws.append_row(row, value_input_option="USER_ENTERED")

    # =========================================================
    # OCR: Transaction rows
    # =========================================================
    def _process_transaction_ocr(
        self,
        file_bytes: bytes,
        source_image: str,
        source_project: str,
        settings_df: pd.DataFrame,
    ) -> None:
        platform = OCRProcessor.detect_platform(file_bytes)

        tx_rows = OCRProcessor.extract_transaction_rows(
            file_bytes=file_bytes,
            settings_df=settings_df,
            project=source_project,
            platform=platform,
        )

        if not tx_rows:
            st.warning("日付・時間・種別・金額を含む取引明細を抽出できませんでした。")
            return

        existing_keys = self._load_existing_ocr_tx_keys()
        created_at = U.fmt_dt(U.now_jst())

        new_sheet_rows: List[List[Any]] = []
        view_rows: List[Dict[str, Any]] = []
        total_detected = 0.0
        total_new = 0.0
        duplicate_count = 0

        for row in tx_rows:
            unique_key = str(row["unique_key"]).strip()
            amount_usd = float(row["amount_usd"])
            is_duplicate = unique_key in existing_keys
            total_detected += amount_usd

            if is_duplicate:
                duplicate_count += 1
            else:
                existing_keys.add(unique_key)
                total_new += amount_usd
                new_sheet_rows.append(
                    [
                        unique_key,
                        row["date_label"],
                        row["time_label"],
                        row["type_label"],
                        amount_usd,
                        "",
                        "",
                        source_image,
                        source_project,
                        row["raw_text"],
                        created_at,
                    ]
                )

            view_rows.append(
                {
                    "Row": row["row_index"],
                    "Date_Label": row["date_label"],
                    "Time_Label": row["time_label"],
                    "Type_Label": row["type_label"],
                    "Amount_USD": f"{amount_usd:.2f}",
                    "Unique_Key": unique_key,
                    "Status": "重複" if is_duplicate else "新規",
                }
            )

        if new_sheet_rows:
            self._append_ocr_tx_rows(new_sheet_rows)

        st.markdown(f"#### 3領域OCR結果 ({platform})")
        self._render_html_table(pd.DataFrame(view_rows))

        c1, c2, c3 = st.columns(3)
        c1.metric("検出合計USD", U.fmt_usd(total_detected))
        c2.metric("新規追加USD", U.fmt_usd(total_new))
        c3.metric("重複件数", str(duplicate_count))

        if new_sheet_rows:
            st.success(f"{len(new_sheet_rows)}件を {self.OCR_TX_HISTORY_SHEET} に保存しました。")
        else:
            st.info("新規追加はありません。すべて重複として除外しました。")

    def _render_transaction_preview_boxes(
        self,
        settings_df: pd.DataFrame,
        project: str,
        file_bytes: bytes,
    ) -> None:
        platform = OCRProcessor.detect_platform(file_bytes)
        preview_boxes = OCRProcessor.build_preview_boxes(
            settings_df=settings_df,
            project=project,
            platform=platform,
            rows_to_show=3,
        )

        st.markdown(f"#### 3領域OCR赤枠プレビュー ({platform})")
        st.image(U.draw_ocr_boxes(file_bytes, preview_boxes), caption="3領域OCR赤枠", width=500)

        layout = OCRProcessor.get_tx_layout(settings_df, project, platform)

        st.markdown(
            f"""
現在の3領域OCR座標（{platform}）
- BaseTop : {layout["base_top"]:.3f}
- Step    : {layout["step"]:.3f}
- MaxRows : {int(layout["max_rows"])}

日付+時間領域
- Left  : {layout["date_left"]:.3f}
- Right : {layout["date_right"]:.3f}

種別領域
- Left  : {layout["type_left"]:.3f}
- Right : {layout["type_right"]:.3f}

USD領域
- Left  : {layout["usd_left"]:.3f}
- Right : {layout["usd_right"]:.3f}
"""
        )

    # =========================================================
    # Main render
    # =========================================================
    def render(self, settings_df: pd.DataFrame, members_df: pd.DataFrame) -> None:
        st.subheader("📈 APR 確定")
        st.caption(
            f"{AppConfig.RANK_LABEL} / PERSONAL=個別計算 / GROUP=総額均等割 / 管理者: {AdminAuth.current_label()}"
        )

        projects = self.repo.active_projects(settings_df)
        if not projects:
            st.warning("有効（Active=TRUE）のプロジェクトがありません。")
            return

        project = st.selectbox("基準プロジェクト", projects)
        send_scope = st.radio("送信対象", ["選択中プロジェクトのみ", "全有効プロジェクト"], horizontal=True)

        st.markdown("#### 流動性 / 昨日の収益 / APR（別取得・手動設定可）")
        c1, c2, c3 = st.columns(3)
        with c1:
            total_liquidity_raw = st.text_input(
                "流動性（手動設定可）",
                value=st.session_state.get("sv_total_liquidity", ""),
                key="sv_total_liquidity",
                placeholder="$78,354.35",
            )
        with c2:
            yesterday_profit_raw = st.text_input(
                "昨日の収益（手動設定可）",
                value=st.session_state.get("sv_yesterday_profit", ""),
                key="sv_yesterday_profit",
                placeholder="$90.87",
            )
        with c3:
            apr_raw = st.text_input(
                "APR（%・手動設定可）",
                value=st.session_state.get("sv_apr", ""),
                key="sv_apr",
                placeholder="42.33",
            )

        total_liquidity = U.to_f(total_liquidity_raw)
        yesterday_profit = U.to_f(yesterday_profit_raw)
        apr = U.apr_val(apr_raw)

        st.info(
            f"流動性 = {U.fmt_usd(total_liquidity)} / "
            f"昨日の収益 = {U.fmt_usd(yesterday_profit)} / "
            f"最終APR = {apr:.4f}%"
        )

        st.markdown("#### フォルダから画像取得して自動OCR（ローカル実行向け）")
        default_watch_folder = self._get_default_watch_folder()
        folder_path = st.text_input(
            "監視フォルダパス",
            value=default_watch_folder,
            key="apr_watch_folder",
            placeholder="/Users/yourname/Desktop/smartvault_images",
        )

        if default_watch_folder:
            st.caption(f"Secrets既定パス: {default_watch_folder}")

        image_files = self._folder_image_files(folder_path) if folder_path else []
        if folder_path and not image_files:
            st.warning("指定フォルダに画像がありません。PNG / JPG / JPEG / WEBP を確認してください。")

        selected_folder_file: Optional[Path] = None
        if image_files:
            labels = [
                f"{p.name}  /  更新: {pd.Timestamp(p.stat().st_mtime, unit='s').strftime('%Y-%m-%d %H:%M:%S')}"
                for p in image_files
            ]
            selected_label = st.selectbox("フォルダ内画像", labels, index=0, key="apr_folder_file_select")
            selected_index = labels.index(selected_label)
            selected_folder_file = image_files[selected_index]

            st.caption(f"最新画像: {image_files[0].name}")

            c_folder1, c_folder2 = st.columns(2)
            with c_folder1:
                if st.button("最新画像を自動OCR", use_container_width=True, key="apr_auto_ocr_latest"):
                    latest_file = image_files[0]
                    try:
                        file_bytes = latest_file.read_bytes()
                        st.session_state["apr_folder_selected_name"] = latest_file.name
                        st.session_state["apr_folder_selected_bytes"] = file_bytes
                        self._apply_ocr_result(file_bytes, settings_df, project)
                        st.rerun()
                    except Exception as e:
                        st.error(f"最新画像OCRでエラー: {e}")

            with c_folder2:
                if st.button("選択画像でOCR", use_container_width=True, key="apr_auto_ocr_selected"):
                    if selected_folder_file is None:
                        st.warning("画像を選択してください。")
                    else:
                        try:
                            file_bytes = selected_folder_file.read_bytes()
                            st.session_state["apr_folder_selected_name"] = selected_folder_file.name
                            st.session_state["apr_folder_selected_bytes"] = file_bytes
                            self._apply_ocr_result(file_bytes, settings_df, project)
                            st.rerun()
                        except Exception as e:
                            st.error(f"選択画像OCRでエラー: {e}")

        st.markdown("#### 手動アップロード")
        uploaded = st.file_uploader("エビデンス画像（任意）", type=["png", "jpg", "jpeg"], key="apr_img")
        if uploaded is not None and st.button("アップロード画像をOCR", key="apr_uploaded_ocr"):
            file_bytes = uploaded.getvalue()
            st.session_state["apr_folder_selected_name"] = uploaded.name
            st.session_state["apr_folder_selected_bytes"] = file_bytes
            self._apply_ocr_result(file_bytes, settings_df, project)
            st.rerun()

        selected_evidence_name = st.session_state.get("apr_folder_selected_name", "")
        selected_evidence_bytes = st.session_state.get("apr_folder_selected_bytes")
        if selected_evidence_name:
            st.caption(f"現在のエビデンス画像: {selected_evidence_name}")

        if selected_evidence_bytes:
            self._render_transaction_preview_boxes(settings_df, project, selected_evidence_bytes)

        st.divider()
        st.markdown("#### 受け取ったUSDC OCR集計（重複防止）")
        st.caption(f"保存先シート: {self.OCR_TX_HISTORY_SHEET}")

        c_tx1, c_tx2 = st.columns(2)
        with c_tx1:
            if st.button("現在の画像から3領域OCR集計", use_container_width=True, key="ocr_tx_current_three"):
                if selected_evidence_bytes:
                    self._process_transaction_ocr(
                        file_bytes=selected_evidence_bytes,
                        source_image=selected_evidence_name or "selected_image",
                        source_project=project,
                        settings_df=settings_df,
                    )
                else:
                    st.warning("先にフォルダ画像を選ぶか、画像をアップロードしてください。")

        with c_tx2:
            if st.button("最新画像から3領域OCR集計", use_container_width=True, key="ocr_tx_latest_three"):
                if image_files:
                    latest_file = image_files[0]
                    try:
                        file_bytes = latest_file.read_bytes()
                        st.session_state["apr_folder_selected_name"] = latest_file.name
                        st.session_state["apr_folder_selected_bytes"] = file_bytes
                        self._process_transaction_ocr(
                            file_bytes=file_bytes,
                            source_image=latest_file.name,
                            source_project=project,
                            settings_df=settings_df,
                        )
                    except Exception as e:
                        st.error(f"最新画像の3領域OCRでエラー: {e}")
                else:
                    st.warning("監視フォルダに画像がありません。")

        target_projects = projects if send_scope == "全有効プロジェクト" else [project]
        today_key = U.fmt_date(U.now_jst())
        existing_apr_keys = self.repo.existing_apr_keys_for_date(today_key)

        preview_rows: List[dict] = []
        total_members = 0
        total_principal = 0.0
        total_reward = 0.0
        skipped_members = 0

        for p in target_projects:
            row = settings_df[settings_df["Project_Name"] == str(p)].iloc[0]
            project_net_factor = float(row.get("Net_Factor", AppConfig.FACTOR["MASTER"]))
            compound_timing = U.normalize_compound(row.get("Compound_Timing", AppConfig.COMPOUND["NONE"]))
            mem = self.repo.project_members_active(members_df, p)
            if mem.empty:
                continue

            mem_calc = self.engine.calc_project_apr(mem, float(apr), project_net_factor, p)
            for _, r in mem_calc.iterrows():
                person = str(r["PersonName"]).strip()
                is_done = (str(p).strip(), person) in existing_apr_keys

                if is_done:
                    skipped_members += 1
                else:
                    total_members += 1
                    total_principal += float(r["Principal"])
                    total_reward += float(r["DailyAPR"])

                preview_rows.append(
                    {
                        "Project_Name": p,
                        "PersonName": person,
                        "Rank": str(r["Rank"]).strip(),
                        "Compound_Timing": U.compound_label(compound_timing),
                        "Principal": U.fmt_usd(float(r["Principal"])),
                        "DailyAPR": U.fmt_usd(float(r["DailyAPR"])),
                        "Line_User_ID": str(r["Line_User_ID"]).strip(),
                        "LINE_DisplayName": str(r["LINE_DisplayName"]).strip(),
                        "流動性": U.fmt_usd(float(total_liquidity)),
                        "昨日の収益": U.fmt_usd(float(yesterday_profit)),
                        "APR": f"{apr:.4f}%",
                        "本日APR状態": "本日記録済み" if is_done else "未記録",
                    }
                )

        if total_members == 0 and skipped_members == 0:
            st.warning("送信対象に 🟢運用中 のメンバーがいません。")
            return

        st.markdown(
            f"送信対象プロジェクト数: {len(target_projects)} / "
            f"本日未記録の対象人数: {total_members} / "
            f"本日記録済み人数: {skipped_members}"
        )

        apr_percent_display = (total_reward / total_principal * 100.0) if total_principal > 0 else 0.0

        csum1, csum2 = st.columns([1.2, 2.8])
        with csum1:
            if send_scope == "選択中プロジェクトのみ":
                if st.button("本日のAPR記録をリセット", key="reset_today_apr_top", use_container_width=True):
                    try:
                        deleted_apr, deleted_line = self.repo.reset_today_apr_records(today_key, project)
                        self.store.persist_and_refresh()
                        if deleted_apr == 0 and deleted_line == 0:
                            st.info("削除対象はありません。")
                        else:
                            st.success(f"本日分をリセットしました。APR削除:{deleted_apr}件 / LINE削除:{deleted_line}件")
                        st.rerun()
                    except Exception as e:
                        st.error(f"APRリセットでエラー: {e}")
                        st.stop()

        with csum2:
            st.markdown(
                f"""
**本日対象サマリー**  
流動性: **{U.fmt_usd(total_liquidity)}**　/　昨日の収益: **{U.fmt_usd(yesterday_profit)}**　/　最終APR: **{apr:.4f}%**  
総投資額: **{U.fmt_usd(total_principal)}**　/　APR合計: **{U.fmt_usd(total_reward)}**　/　実効APR: **{apr_percent_display:.4f}%**
"""
            )

        with st.expander("個人別の本日配当（確認）", expanded=False):
            self._render_html_table(pd.DataFrame(preview_rows))
