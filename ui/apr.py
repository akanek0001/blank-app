from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import re

import pandas as pd
import streamlit as st

from config import AppConfig
from core.auth import AdminAuth
from core.utils import U
from engine.finance_engine import FinanceEngine
from repository.repository import Repository
from services.external_service import ExternalService
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
    # OCR / SmartVault
    # =========================================================
    def _ocr_crop_text(self, file_bytes: bytes, box: Dict[str, float]) -> str:
        return ExternalService.ocr_space_extract_text_with_crop(
            file_bytes=file_bytes,
            crop_left_ratio=box["left"],
            crop_top_ratio=box["top"],
            crop_right_ratio=box["right"],
            crop_bottom_ratio=box["bottom"],
        )

    def _ocr_smartvault_mobile_metrics(self, file_bytes: bytes) -> Dict[str, Any]:
        boxes = AppConfig.SMARTVAULT_BOXES_MOBILE
        total_text = self._ocr_crop_text(file_bytes, boxes["TOTAL_LIQUIDITY"])
        profit_text = self._ocr_crop_text(file_bytes, boxes["YESTERDAY_PROFIT"])
        apr_text = self._ocr_crop_text(file_bytes, boxes["APR"])
        total_vals = U.extract_usd_candidates(total_text)
        profit_vals = U.extract_usd_candidates(profit_text)
        apr_vals = U.extract_percent_candidates(apr_text)
        total_liquidity = U.pick_total_liquidity(total_vals)
        yesterday_profit = U.pick_yesterday_profit(profit_vals)
        apr_value = apr_vals[0] if apr_vals else None
        boxed_preview = U.draw_ocr_boxes(file_bytes, boxes)
        return {
            "boxes": boxes,
            "total_text": total_text,
            "profit_text": profit_text,
            "apr_text": apr_text,
            "total_vals": total_vals,
            "profit_vals": profit_vals,
            "apr_vals": apr_vals,
            "total_liquidity": total_liquidity,
            "yesterday_profit": yesterday_profit,
            "apr_value": apr_value,
            "boxed_preview": boxed_preview,
        }

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

    def _get_crop_ratios(self, settings_df: pd.DataFrame, project: str, file_bytes: bytes) -> Tuple[float, float, float, float]:
        crop_left_ratio = AppConfig.OCR_DEFAULTS_PC["Crop_Left_Ratio_PC"]
        crop_top_ratio = AppConfig.OCR_DEFAULTS_PC["Crop_Top_Ratio_PC"]
        crop_right_ratio = AppConfig.OCR_DEFAULTS_PC["Crop_Right_Ratio_PC"]
        crop_bottom_ratio = AppConfig.OCR_DEFAULTS_PC["Crop_Bottom_Ratio_PC"]

        try:
            srow = settings_df[settings_df["Project_Name"] == str(project)].iloc[0]
            if U.is_mobile_tall_image(file_bytes):
                crop_left_ratio = U.to_ratio(
                    srow.get("Crop_Left_Ratio_Mobile", AppConfig.OCR_DEFAULTS_MOBILE["Crop_Left_Ratio_Mobile"]),
                    AppConfig.OCR_DEFAULTS_MOBILE["Crop_Left_Ratio_Mobile"],
                )
                crop_top_ratio = U.to_ratio(
                    srow.get("Crop_Top_Ratio_Mobile", AppConfig.OCR_DEFAULTS_MOBILE["Crop_Top_Ratio_Mobile"]),
                    AppConfig.OCR_DEFAULTS_MOBILE["Crop_Top_Ratio_Mobile"],
                )
                crop_right_ratio = U.to_ratio(
                    srow.get("Crop_Right_Ratio_Mobile", AppConfig.OCR_DEFAULTS_MOBILE["Crop_Right_Ratio_Mobile"]),
                    AppConfig.OCR_DEFAULTS_MOBILE["Crop_Right_Ratio_Mobile"],
                )
                crop_bottom_ratio = U.to_ratio(
                    srow.get("Crop_Bottom_Ratio_Mobile", AppConfig.OCR_DEFAULTS_MOBILE["Crop_Bottom_Ratio_Mobile"]),
                    AppConfig.OCR_DEFAULTS_MOBILE["Crop_Bottom_Ratio_Mobile"],
                )
            else:
                crop_left_ratio = U.to_ratio(
                    srow.get("Crop_Left_Ratio_PC", AppConfig.OCR_DEFAULTS_PC["Crop_Left_Ratio_PC"]),
                    AppConfig.OCR_DEFAULTS_PC["Crop_Left_Ratio_PC"],
                )
                crop_top_ratio = U.to_ratio(
                    srow.get("Crop_Top_Ratio_PC", AppConfig.OCR_DEFAULTS_PC["Crop_Top_Ratio_PC"]),
                    AppConfig.OCR_DEFAULTS_PC["Crop_Top_Ratio_PC"],
                )
                crop_right_ratio = U.to_ratio(
                    srow.get("Crop_Right_Ratio_PC", AppConfig.OCR_DEFAULTS_PC["Crop_Right_Ratio_PC"]),
                    AppConfig.OCR_DEFAULTS_PC["Crop_Right_Ratio_PC"],
                )
                crop_bottom_ratio = U.to_ratio(
                    srow.get("Crop_Bottom_Ratio_PC", AppConfig.OCR_DEFAULTS_PC["Crop_Bottom_Ratio_PC"]),
                    AppConfig.OCR_DEFAULTS_PC["Crop_Bottom_Ratio_PC"],
                )
        except Exception:
            pass

        return crop_left_ratio, crop_top_ratio, crop_right_ratio, crop_bottom_ratio

    def _apply_ocr_result(self, file_bytes: bytes, settings_df: pd.DataFrame, project: str) -> None:
        crop_left_ratio, crop_top_ratio, crop_right_ratio, crop_bottom_ratio = self._get_crop_ratios(settings_df, project, file_bytes)

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
            f"OCR切り抜き範囲: left={crop_left_ratio:.3f}, top={crop_top_ratio:.3f}, right={crop_right_ratio:.3f}, bottom={crop_bottom_ratio:.3f}"
        )

        if U.is_mobile_tall_image(file_bytes):
            smart = self._ocr_smartvault_mobile_metrics(file_bytes)

            st.markdown("#### SmartVaultモバイル専用OCR結果")
            st.image(smart["boxed_preview"], caption="赤枠 = OCR対象範囲", use_container_width=True)

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
        else:
            apr_candidates = U.extract_percent_candidates(raw_text)
            if apr_candidates:
                best = apr_candidates[0]
                st.success(f"通常OCRからAPR候補を検出: {best}%")
                st.session_state["sv_apr"] = f"{float(best):.4f}"
                st.session_state["ocr_apr"] = float(best)
            else:
                st.warning("APR候補は見つかりませんでした。")

    # =========================================================
    # OCR Transaction History
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
        out = set()
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

    def _ocr_full_text(self, file_bytes: bytes) -> str:
        return ExternalService.ocr_space_extract_text_with_crop(
            file_bytes=file_bytes,
            crop_left_ratio=0.0,
            crop_top_ratio=0.0,
            crop_right_ratio=1.0,
            crop_bottom_ratio=1.0,
        )

    def _normalize_spaces(self, text: str) -> str:
        return re.sub(r"[ \t\u3000]+", " ", str(text)).strip()

    def _normalize_type_label(self, text: str) -> str:
        t = self._normalize_spaces(text)
        if "受け取ったUSDC" in t:
            return "受け取ったUSDC"
        if "トークンを受け取りました" in t:
            return "トークンを受け取りました"
        if "USDC" in t:
            return "USDC"
        return t

    def _extract_tx_blocks(self, raw_text: str) -> List[Dict[str, Any]]:
        text = str(raw_text or "").replace("\r\n", "\n").replace("\r", "\n")
        lines = [self._normalize_spaces(x) for x in text.split("\n")]
        lines = [x for x in lines if x]

        blocks: List[Dict[str, Any]] = []
        current: Optional[Dict[str, Any]] = None

        date_time_re = re.compile(
            r"(?P<date>(?:\d{1,2}\s*月\s*\d{1,2})|(?:\d{1,2}/\d{1,2})|(?:\d{1,2}-\d{1,2})|(?:[A-Za-z]{3,9}\s+\d{1,2})|(?:\d{1,2}\s+\d{1,2}))\s*(?:at)?\s*(?P<time>\d{1,2}:\d{2}\s*(?:am|pm|AM|PM))"
        )

        usd_line_re = re.compile(r"\$?\s*(\d+(?:,\d{3})*(?:\.\d+)?)")
        token_line_re = re.compile(r"(\d+(?:,\d{3})*(?:\.\d+)?)\s*([A-Za-z]{2,10})")

        for line in lines:
            m = date_time_re.search(line)
            if m:
                if current:
                    blocks.append(current)
                current = {
                    "date_label": self._normalize_spaces(m.group("date")),
                    "time_label": self._normalize_spaces(m.group("time")).lower(),
                    "type_label": "",
                    "amount_usd": None,
                    "token_amount": None,
                    "token_symbol": "",
                    "raw_lines": [line],
                }
                continue

            if current is None:
                continue

            current["raw_lines"].append(line)

            if ("USDC" in line or "トークン" in line or "受け取" in line) and not current["type_label"]:
                current["type_label"] = self._normalize_type_label(line)

            if "$" in line and current["amount_usd"] is None:
                m_usd = usd_line_re.search(line)
                if m_usd:
                    current["amount_usd"] = float(str(m_usd.group(1)).replace(",", ""))

            if current["token_amount"] is None:
                m_token = token_line_re.search(line)
                if m_token:
                    amt = float(str(m_token.group(1)).replace(",", ""))
                    sym = str(m_token.group(2)).upper().strip()
                    if sym in {"USDC", "ETH", "BTC", "USDT"}:
                        current["token_amount"] = amt
                        current["token_symbol"] = sym

        if current:
            blocks.append(current)

        cleaned: List[Dict[str, Any]] = []
        for b in blocks:
            type_label = str(b.get("type_label", "")).strip()
            amount_usd = b.get("amount_usd")
            token_symbol = str(b.get("token_symbol", "")).strip()

            joined = " ".join(b.get("raw_lines", []))

            if amount_usd is None:
                continue
            if float(amount_usd) <= 0:
                continue
            if "承認" in joined:
                continue
            if not type_label and "USDC" in joined:
                type_label = "受け取ったUSDC"
            if not type_label:
                continue
            if "USDC" not in joined and "トークン" not in type_label and "受け取" not in type_label:
                continue

            b["type_label"] = type_label
            if not token_symbol and "USDC" in joined:
                b["token_symbol"] = "USDC"
            cleaned.append(b)

        return cleaned

    def _make_tx_unique_key(self, date_label: str, time_label: str, type_label: str, amount_usd: float) -> str:
        return f"{date_label}|{time_label}|{type_label}|{float(amount_usd):.2f}"

    def _process_transaction_ocr(self, file_bytes: bytes, source_image: str, source_project: str) -> None:
        raw_text = self._ocr_full_text(file_bytes)

        with st.expander("取引OCR生テキスト", expanded=False):
            st.text(raw_text or "")

        blocks = self._extract_tx_blocks(raw_text)
        if not blocks:
            st.warning("受け取ったUSDCの明細を抽出できませんでした。")
            return

        existing_keys = self._load_existing_ocr_tx_keys()
        new_rows: List[List[Any]] = []
        view_rows: List[Dict[str, Any]] = []

        total_all = 0.0
        total_new = 0.0
        duplicate_count = 0

        created_at = U.fmt_dt(U.now_jst())

        for b in blocks:
            date_label = str(b.get("date_label", "")).strip()
            time_label = str(b.get("time_label", "")).strip()
            type_label = str(b.get("type_label", "")).strip()
            amount_usd = float(b.get("amount_usd") or 0.0)
            token_amount = "" if b.get("token_amount") is None else float(b.get("token_amount"))
            token_symbol = str(b.get("token_symbol", "")).strip()
            unique_key = self._make_tx_unique_key(date_label, time_label, type_label, amount_usd)

            is_duplicate = unique_key in existing_keys
            total_all += amount_usd

            if is_duplicate:
                duplicate_count += 1
            else:
                total_new += amount_usd
                existing_keys.add(unique_key)
                new_rows.append(
                    [
                        unique_key,
                        date_label,
                        time_label,
                        type_label,
                        float(amount_usd),
                        token_amount,
                        token_symbol,
                        source_image,
                        source_project,
                        raw_text,
                        created_at,
                    ]
                )

            view_rows.append(
                {
                    "Date_Label": date_label,
                    "Time_Label": time_label,
                    "Type_Label": type_label,
                    "Amount_USD": f"{amount_usd:.2f}",
                    "Token_Amount": token_amount,
                    "Token_Symbol": token_symbol,
                    "Unique_Key": unique_key,
                    "Status": "重複" if is_duplicate else "新規",
                }
            )

        if new_rows:
            self._append_ocr_tx_rows(new_rows)

        st.markdown("#### OCR取引抽出結果")
        st.dataframe(pd.DataFrame(view_rows), use_container_width=True, hide_index=True)

        c1, c2, c3 = st.columns(3)
        c1.metric("検出合計USD", U.fmt_usd(total_all))
        c2.metric("新規追加USD", U.fmt_usd(total_new))
        c3.metric("重複件数", str(duplicate_count))

        if new_rows:
            st.success(f"{len(new_rows)}件を {self.OCR_TX_HISTORY_SHEET} に保存しました。")
        else:
            st.info("新規追加はありません。すべて重複として除外しました。")

    # =========================================================
    # Main Render
    # =========================================================
    def render(self, settings_df: pd.DataFrame, members_df: pd.DataFrame) -> None:
        st.subheader("📈 APR 確定")
        st.caption(f"{AppConfig.RANK_LABEL} / PERSONAL=個別計算 / GROUP=総額均等割 / 管理者: {AdminAuth.current_label()}")

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
            labels = [f"{p.name}  /  更新: {pd.Timestamp(p.stat().st_mtime, unit='s').strftime('%Y-%m-%d %H:%M:%S')}" for p in image_files]
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

            if selected_folder_file is not None:
                try:
                    preview_bytes = selected_folder_file.read_bytes()
                    st.image(preview_bytes, caption=f"フォルダ画像プレビュー: {selected_folder_file.name}", use_container_width=True)
                except Exception:
                    pass

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

        st.divider()
        st.markdown("#### 受け取ったUSDC OCR集計（重複防止）")
        st.caption(f"保存先シート: {self.OCR_TX_HISTORY_SHEET}")

        c_tx1, c_tx2 = st.columns(2)
        with c_tx1:
            if st.button("現在の画像から取引OCR集計", use_container_width=True, key="ocr_tx_current"):
                if selected_evidence_bytes:
                    self._process_transaction_ocr(
                        selected_evidence_bytes,
                        selected_evidence_name or "selected_image",
                        project,
                    )
                else:
                    st.warning("先にフォルダ画像を選ぶか、画像をアップロードしてください。")

        with c_tx2:
            if st.button("最新画像から取引OCR集計", use_container_width=True, key="ocr_tx_latest"):
                if image_files:
                    latest_file = image_files[0]
                    try:
                        file_bytes = latest_file.read_bytes()
                        st.session_state["apr_folder_selected_name"] = latest_file.name
                        st.session_state["apr_folder_selected_bytes"] = file_bytes
                        self._process_transaction_ocr(file_bytes, latest_file.name, project)
                    except Exception as e:
                        st.error(f"最新画像の取引OCRでエラー: {e}")
                else:
                    st.warning("監視フォルダに画像がありません。")

        target_projects = projects if send_scope == "全有効プロジェクト" else [project]
        today_key = U.fmt_date(U.now_jst())
        existing_apr_keys = self.repo.existing_apr_keys_for_date(today_key)

        preview_rows: List[dict] = []
        total_members, total_principal, total_reward, skipped_members = 0, 0.0, 0.0, 0

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

        st.markdown(f"送信対象プロジェクト数: {len(target_projects)} / 本日未記録の対象人数: {total_members} / 本日記録済み人数: {skipped_members}")

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
            st.dataframe(pd.DataFrame(preview_rows), use_container_width=True, hide_index=True)

        if st.button("APRを確定して対象全員にLINE送信"):
            try:
                if apr <= 0:
                    st.warning("APRが0以下です。")
                    return

                evidence_url = None
                evidence_file_bytes: Optional[bytes] = None

                if uploaded is not None:
                    evidence_file_bytes = uploaded.getvalue()
                elif selected_evidence_bytes:
                    evidence_file_bytes = selected_evidence_bytes

                if evidence_file_bytes:
                    evidence_url = ExternalService.upload_imgbb(evidence_file_bytes)
                    if not evidence_url:
                        st.error("画像アップロードに失敗しました。")
                        return

                source_mode = U.detect_source_mode(
                    final_liquidity=float(total_liquidity),
                    final_profit=float(yesterday_profit),
                    final_apr=float(apr),
                    ocr_liquidity=st.session_state.get("ocr_total_liquidity"),
                    ocr_profit=st.session_state.get("ocr_yesterday_profit"),
                    ocr_apr=st.session_state.get("ocr_apr"),
                )

                ts = U.fmt_dt(U.now_jst())
                apr_ledger_count, line_log_count, success, fail, skip_count = 0, 0, 0, 0, 0
                existing_apr_keys = self.repo.existing_apr_keys_for_date(today_key)
                token = ExternalService.get_line_token(AdminAuth.current_namespace())
                daily_add_map: Dict[Tuple[str, str], float] = {}

                self.repo.append_smartvault_history(
                    ts,
                    project,
                    float(total_liquidity),
                    float(yesterday_profit),
                    float(apr),
                    source_mode,
                    st.session_state.get("ocr_total_liquidity"),
                    st.session_state.get("ocr_yesterday_profit"),
                    st.session_state.get("ocr_apr"),
                    evidence_url or "",
                    AdminAuth.current_name(),
                    AdminAuth.current_namespace(),
                    f"APR確定時に保存 / Evidence:{selected_evidence_name}" if selected_evidence_name else "APR確定時に保存",
                )

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
                        uid = str(r["Line_User_ID"]).strip()
                        disp = str(r["LINE_DisplayName"]).strip()
                        daily_apr = float(r["DailyAPR"])
                        current_principal = float(r["Principal"])
                        apr_key = (str(p).strip(), person)

                        if apr_key in existing_apr_keys:
                            skip_count += 1
                            continue

                        note = (
                            f"APR:{apr}%, "
                            f"Liquidity:{total_liquidity}, "
                            f"YesterdayProfit:{yesterday_profit}, "
                            f"SourceMode:{source_mode}, "
                            f"Mode:{r['CalcMode']}, Rank:{r['Rank']}, Factor:{r['Factor']}, CompoundTiming:{compound_timing}"
                        )
                        self.repo.append_ledger(ts, p, person, AppConfig.TYPE["APR"], daily_apr, note, evidence_url or "", uid, disp)
                        existing_apr_keys.add(apr_key)
                        apr_ledger_count += 1

                        if compound_timing == AppConfig.COMPOUND["DAILY"]:
                            daily_add_map[(str(p).strip(), person)] = daily_add_map.get((str(p).strip(), person), 0.0) + daily_apr
                            person_after_amount = current_principal + daily_apr
                        else:
                            person_after_amount = current_principal

                        personalized_msg = (
                            "🏦【APR収益報告】\n"
                            f"{person} 様\n"
                            f"報告日時: {U.now_jst().strftime('%Y/%m/%d %H:%M')}\n"
                            f"流動性: {U.fmt_usd(total_liquidity)}\n"
                            f"昨日の収益: {U.fmt_usd(yesterday_profit)}\n"
                            f"APR: {apr:.4f}%\n"
                            f"本日配当: {U.fmt_usd(daily_apr)}\n"
                            f"現在運用額: {U.fmt_usd(current_principal)}\n"
                            f"複利タイプ: {U.compound_label(compound_timing)}\n"
                        )

                        if compound_timing == AppConfig.COMPOUND["DAILY"]:
                            personalized_msg += f"複利反映後運用額: {U.fmt_usd(person_after_amount)}\n"

                        if not uid:
                            code, line_note = 0, "LINE未送信: Line_User_IDなし"
                        else:
                            code = ExternalService.send_line_push(token, uid, personalized_msg, evidence_url)
                            line_note = (
                                f"HTTP:{code}, "
                                f"Liquidity:{total_liquidity}, "
                                f"YesterdayProfit:{yesterday_profit}, "
                                f"APR:{apr}%, SourceMode:{source_mode}, CompoundTiming:{compound_timing}"
                            )

                        self.repo.append_ledger(ts, p, person, AppConfig.TYPE["LINE"], 0, line_note, evidence_url or "", uid, disp)
                        line_log_count += 1

                        if code == 200:
                            success += 1
                        else:
                            fail += 1

                if daily_add_map:
                    for i in range(len(members_df)):
                        p = str(members_df.loc[i, "Project_Name"]).strip()
                        pn = str(members_df.loc[i, "PersonName"]).strip()
                        addv = float(daily_add_map.get((p, pn), 0.0))
                        if addv != 0.0 and U.truthy(members_df.loc[i, "IsActive"]):
                            members_df.loc[i, "Principal"] = float(members_df.loc[i, "Principal"]) + addv
                            members_df.loc[i, "UpdatedAt_JST"] = ts
                    self.repo.write_members(members_df)

                self.store.persist_and_refresh()
                st.success(
                    f"APR記録:{apr_ledger_count}件 / LINE履歴記録:{line_log_count}件 / "
                    f"送信成功:{success} / 送信失敗:{fail} / 重複スキップ:{skip_count}件"
                )
                st.rerun()

            except Exception as e:
                st.error(f"APR確定処理でエラー: {e}")
                st.stop()

        if send_scope == "選択中プロジェクトのみ":
            row = settings_df[settings_df["Project_Name"] == str(project)].iloc[0]
            compound_timing = U.normalize_compound(row.get("Compound_Timing", AppConfig.COMPOUND["NONE"]))
            if compound_timing == AppConfig.COMPOUND["MONTHLY"]:
                st.divider()
                st.markdown("#### 月次複利反映")
                if st.button("未反映APRを元本へ反映"):
                    try:
                        count, total_added = self.engine.apply_monthly_compound(self.repo, members_df, project)
                        self.store.persist_and_refresh()
                        if count == 0:
                            st.info("未反映のAPRはありません。")
                        else:
                            st.success(f"{count}名に反映しました。合計反映額: {U.fmt_usd(total_added)}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"月次複利反映でエラー: {e}")
                        st.stop()
