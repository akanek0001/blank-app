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
        "Platform",
        "OCR_Raw_Text",
        "CreatedAt_JST",
    ]

    # =========================================================
    # MOBILE: 1170 x 2532 基準 / 3領域OCR
    # =========================================================
    MOBILE_TX_SCAN_BASE_TOP_RATIO = 430 / 2532
    MOBILE_TX_SCAN_STEP_RATIO = 123 / 2532
    MOBILE_TX_SCAN_MAX_ROWS = 10

    MOBILE_TX_DATE_LEFT = 25 / 1170
    MOBILE_TX_DATE_RIGHT = 470 / 1170
    MOBILE_TX_DATE_TOP_OFFSET = 0 / 2532
    MOBILE_TX_DATE_BOTTOM_OFFSET = 70 / 2532

    MOBILE_TX_TYPE_LEFT = 100 / 1170
    MOBILE_TX_TYPE_RIGHT = 760 / 1170
    MOBILE_TX_TYPE_TOP_OFFSET = 38 / 2532
    MOBILE_TX_TYPE_BOTTOM_OFFSET = 125 / 2532

    MOBILE_TX_USD_LEFT = 760 / 1170
    MOBILE_TX_USD_RIGHT = 1090 / 1170
    MOBILE_TX_USD_TOP_OFFSET = 28 / 2532
    MOBILE_TX_USD_BOTTOM_OFFSET = 92 / 2532

    # =========================================================
    # PC: 初期値（必要に応じて Settings__* で上書き）
    # =========================================================
    PC_TX_SCAN_BASE_TOP_RATIO = 0.18
    PC_TX_SCAN_STEP_RATIO = 0.08
    PC_TX_SCAN_MAX_ROWS = 12

    PC_TX_DATE_LEFT = 0.04
    PC_TX_DATE_RIGHT = 0.28
    PC_TX_DATE_TOP_OFFSET = 0.00
    PC_TX_DATE_BOTTOM_OFFSET = 0.05

    PC_TX_TYPE_LEFT = 0.10
    PC_TX_TYPE_RIGHT = 0.48
    PC_TX_TYPE_TOP_OFFSET = 0.03
    PC_TX_TYPE_BOTTOM_OFFSET = 0.10

    PC_TX_USD_LEFT = 0.72
    PC_TX_USD_RIGHT = 0.94
    PC_TX_USD_TOP_OFFSET = 0.02
    PC_TX_USD_BOTTOM_OFFSET = 0.08

    def __init__(self, repo: Repository, engine: FinanceEngine, store: DataStore):
        self.repo = repo
        self.engine = engine
        self.store = store

    # =========================================================
    # 基本ユーティリティ
    # =========================================================
    def _normalize_ocr_text(self, text: str) -> str:
        t = str(text or "")
        t = t.replace("月 ", "月")
        t = t.replace(" 日", "日")
        t = t.replace(" at ", " ")
        t = t.replace("午前", "am")
        t = t.replace("午後", "pm")
        t = re.sub(r"[ \t\u3000]+", " ", t)
        return t.strip()

    def _detect_platform(self, file_bytes: Optional[bytes]) -> str:
        if not file_bytes:
            return "mobile"
        try:
            return "mobile" if U.is_mobile_tall_image(file_bytes) else "pc"
        except Exception:
            return "mobile"

    def _ocr_crop_text(self, file_bytes: bytes, box: Dict[str, float]) -> str:
        return ExternalService.ocr_space_extract_text_with_crop(
            file_bytes=file_bytes,
            crop_left_ratio=float(box["left"]),
            crop_top_ratio=float(box["top"]),
            crop_right_ratio=float(box["right"]),
            crop_bottom_ratio=float(box["bottom"]),
        )

    def _row_top_ratio(self, base_top: float, step: float, row_index: int) -> float:
        return base_top + (step * row_index)

    def _build_region_box(
        self,
        row_top: float,
        left_ratio: float,
        right_ratio: float,
        top_offset_ratio: float,
        bottom_offset_ratio: float,
    ) -> Dict[str, float]:
        return {
            "left": float(left_ratio),
            "top": float(row_top + top_offset_ratio),
            "right": float(right_ratio),
            "bottom": float(row_top + bottom_offset_ratio),
        }

    def _extract_date_label(self, text: str) -> str:
        t = self._normalize_ocr_text(text)
        patterns = [
            r"(\d{1,2}\s*月\s*\d{1,2}\s*日)",
            r"(\d{1,2}\s*月\s*\d{1,2})",
            r"(\d{1,2}/\d{1,2})",
            r"(\d{1,2}-\d{1,2})",
        ]
        for pat in patterns:
            m = re.search(pat, t)
            if m:
                return self._normalize_ocr_text(m.group(1)).replace(" ", "")
        return ""

    def _extract_time_label(self, text: str) -> str:
        t = self._normalize_ocr_text(text)
        patterns = [
            r"(\d{1,2}:\d{2}\s*(?:am|pm|AM|PM))",
            r"(\d{1,2}:\d{2})",
        ]
        for pat in patterns:
            m = re.search(pat, t)
            if m:
                return self._normalize_ocr_text(m.group(1)).lower()
        return ""

    def _extract_type_label(self, text: str) -> str:
        t = self._normalize_ocr_text(text)
        if "受け取ったUSDC" in t or "受け取った USDC" in t:
            return "受け取ったUSDC"
        if "トークンを受け取りました" in t:
            return "トークンを受け取りました"
        if "承認" in t:
            return "承認"
        if "USDC" in t:
            return "USDC"
        return ""

    def _extract_amount_usd(self, text: str) -> Optional[float]:
        t = self._normalize_ocr_text(text)
        m = re.search(r"\$\s*(\d+(?:,\d{3})*(?:\.\d+)?)", t)
        if m:
            try:
                return float(m.group(1).replace(",", ""))
            except Exception:
                return None

        vals = U.extract_usd_candidates(t)
        if vals:
            positives = [float(v) for v in vals if float(v) >= 0]
            if positives:
                return max(positives)
        return None

    def _extract_token_amount_and_symbol(self, text: str) -> Tuple[Optional[float], str]:
        t = self._normalize_ocr_text(text)
        patterns = [
            r"(\d+(?:,\d{3})*(?:\.\d+)?)\s*(USDC|ETH|BTC|USDT)",
            r"(USDC|ETH|BTC|USDT)\s*(\d+(?:,\d{3})*(?:\.\d+)?)",
        ]
        for pat in patterns:
            m = re.search(pat, t, flags=re.IGNORECASE)
            if not m:
                continue
            g1 = str(m.group(1)).strip()
            g2 = str(m.group(2)).strip()
            try:
                if re.match(r"^\d", g1):
                    return float(g1.replace(",", "")), g2.upper()
                return float(g2.replace(",", "")), g1.upper()
            except Exception:
                continue
        return None, ""

    def _make_tx_block_key(self, date_label: str, time_label: str, type_label: str, amount_usd: float, platform: str) -> str:
        return f"{platform}|{date_label}|{time_label}|{type_label}|{float(amount_usd):.2f}"

    # =========================================================
    # Settings 読み取り
    # =========================================================
    def _get_setting_row(self, settings_df: pd.DataFrame, project: str) -> Optional[pd.Series]:
        try:
            return settings_df[settings_df["Project_Name"] == str(project)].iloc[0]
        except Exception:
            return None

    def _get_general_crop_ratios(
        self,
        settings_df: pd.DataFrame,
        project: str,
        platform: str,
    ) -> Tuple[float, float, float, float]:
        srow = self._get_setting_row(settings_df, project)
        if platform == "mobile":
            d = AppConfig.OCR_DEFAULTS_MOBILE
            if srow is None:
                return (
                    float(d["Crop_Left_Ratio_Mobile"]),
                    float(d["Crop_Top_Ratio_Mobile"]),
                    float(d["Crop_Right_Ratio_Mobile"]),
                    float(d["Crop_Bottom_Ratio_Mobile"]),
                )
            return (
                U.to_ratio(srow.get("Crop_Left_Ratio_Mobile", d["Crop_Left_Ratio_Mobile"]), d["Crop_Left_Ratio_Mobile"]),
                U.to_ratio(srow.get("Crop_Top_Ratio_Mobile", d["Crop_Top_Ratio_Mobile"]), d["Crop_Top_Ratio_Mobile"]),
                U.to_ratio(srow.get("Crop_Right_Ratio_Mobile", d["Crop_Right_Ratio_Mobile"]), d["Crop_Right_Ratio_Mobile"]),
                U.to_ratio(srow.get("Crop_Bottom_Ratio_Mobile", d["Crop_Bottom_Ratio_Mobile"]), d["Crop_Bottom_Ratio_Mobile"]),
            )

        d = AppConfig.OCR_DEFAULTS_PC
        if srow is None:
            return (
                float(d["Crop_Left_Ratio_PC"]),
                float(d["Crop_Top_Ratio_PC"]),
                float(d["Crop_Right_Ratio_PC"]),
                float(d["Crop_Bottom_Ratio_PC"]),
            )
        return (
            U.to_ratio(srow.get("Crop_Left_Ratio_PC", d["Crop_Left_Ratio_PC"]), d["Crop_Left_Ratio_PC"]),
            U.to_ratio(srow.get("Crop_Top_Ratio_PC", d["Crop_Top_Ratio_PC"]), d["Crop_Top_Ratio_PC"]),
            U.to_ratio(srow.get("Crop_Right_Ratio_PC", d["Crop_Right_Ratio_PC"]), d["Crop_Right_Ratio_PC"]),
            U.to_ratio(srow.get("Crop_Bottom_Ratio_PC", d["Crop_Bottom_Ratio_PC"]), d["Crop_Bottom_Ratio_PC"]),
        )

    def _get_smartvault_boxes(self, settings_df: pd.DataFrame, project: str, platform: str) -> Dict[str, Dict[str, float]]:
        srow = self._get_setting_row(settings_df, project)

        if platform == "mobile":
            default_boxes = {
                "TOTAL_LIQUIDITY": {"left": 0.05, "top": 0.25, "right": 0.40, "bottom": 0.34},
                "YESTERDAY_PROFIT": {"left": 0.41, "top": 0.25, "right": 0.69, "bottom": 0.34},
                "APR": {"left": 0.70, "top": 0.25, "right": 0.93, "bottom": 0.34},
            }
            if srow is None:
                return default_boxes

            return {
                "TOTAL_LIQUIDITY": {
                    "left": float(srow.get("SV_Total_Liquidity_Left", default_boxes["TOTAL_LIQUIDITY"]["left"])),
                    "top": float(srow.get("SV_Total_Liquidity_Top", default_boxes["TOTAL_LIQUIDITY"]["top"])),
                    "right": float(srow.get("SV_Total_Liquidity_Right", default_boxes["TOTAL_LIQUIDITY"]["right"])),
                    "bottom": float(srow.get("SV_Total_Liquidity_Bottom", default_boxes["TOTAL_LIQUIDITY"]["bottom"])),
                },
                "YESTERDAY_PROFIT": {
                    "left": float(srow.get("SV_Yesterday_Profit_Left", default_boxes["YESTERDAY_PROFIT"]["left"])),
                    "top": float(srow.get("SV_Yesterday_Profit_Top", default_boxes["YESTERDAY_PROFIT"]["top"])),
                    "right": float(srow.get("SV_Yesterday_Profit_Right", default_boxes["YESTERDAY_PROFIT"]["right"])),
                    "bottom": float(srow.get("SV_Yesterday_Profit_Bottom", default_boxes["YESTERDAY_PROFIT"]["bottom"])),
                },
                "APR": {
                    "left": float(srow.get("SV_APR_Left", default_boxes["APR"]["left"])),
                    "top": float(srow.get("SV_APR_Top", default_boxes["APR"]["top"])),
                    "right": float(srow.get("SV_APR_Right", default_boxes["APR"]["right"])),
                    "bottom": float(srow.get("SV_APR_Bottom", default_boxes["APR"]["bottom"])),
                },
            }

        default_boxes = {
            "TOTAL_LIQUIDITY": {"left": 0.05, "top": 0.18, "right": 0.35, "bottom": 0.27},
            "YESTERDAY_PROFIT": {"left": 0.36, "top": 0.18, "right": 0.62, "bottom": 0.27},
            "APR": {"left": 0.63, "top": 0.18, "right": 0.85, "bottom": 0.27},
        }
        if srow is None:
            return default_boxes

        return {
            "TOTAL_LIQUIDITY": {
                "left": float(srow.get("SV_Total_Liquidity_Left_PC", default_boxes["TOTAL_LIQUIDITY"]["left"])),
                "top": float(srow.get("SV_Total_Liquidity_Top_PC", default_boxes["TOTAL_LIQUIDITY"]["top"])),
                "right": float(srow.get("SV_Total_Liquidity_Right_PC", default_boxes["TOTAL_LIQUIDITY"]["right"])),
                "bottom": float(srow.get("SV_Total_Liquidity_Bottom_PC", default_boxes["TOTAL_LIQUIDITY"]["bottom"])),
            },
            "YESTERDAY_PROFIT": {
                "left": float(srow.get("SV_Yesterday_Profit_Left_PC", default_boxes["YESTERDAY_PROFIT"]["left"])),
                "top": float(srow.get("SV_Yesterday_Profit_Top_PC", default_boxes["YESTERDAY_PROFIT"]["top"])),
                "right": float(srow.get("SV_Yesterday_Profit_Right_PC", default_boxes["YESTERDAY_PROFIT"]["right"])),
                "bottom": float(srow.get("SV_Yesterday_Profit_Bottom_PC", default_boxes["YESTERDAY_PROFIT"]["bottom"])),
            },
            "APR": {
                "left": float(srow.get("SV_APR_Left_PC", default_boxes["APR"]["left"])),
                "top": float(srow.get("SV_APR_Top_PC", default_boxes["APR"]["top"])),
                "right": float(srow.get("SV_APR_Right_PC", default_boxes["APR"]["right"])),
                "bottom": float(srow.get("SV_APR_Bottom_PC", default_boxes["APR"]["bottom"])),
            },
        }

    # =========================================================
    # SmartVault OCR
    # =========================================================
    def _ocr_smartvault_metrics(self, file_bytes: bytes, boxes: Dict[str, Dict[str, float]]) -> Dict[str, Any]:
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
            "total_liquidity": total_liquidity,
            "yesterday_profit": yesterday_profit,
            "apr_value": apr_value,
            "boxed_preview": boxed_preview,
        }

    def _apply_platform_ocr_result(self, file_bytes: bytes, settings_df: pd.DataFrame, project: str, platform: str) -> None:
        crop_left_ratio, crop_top_ratio, crop_right_ratio, crop_bottom_ratio = self._get_general_crop_ratios(
            settings_df, project, platform
        )

        raw_text = ExternalService.ocr_space_extract_text_with_crop(
            file_bytes=file_bytes,
            crop_left_ratio=crop_left_ratio,
            crop_top_ratio=crop_top_ratio,
            crop_right_ratio=crop_right_ratio,
            crop_bottom_ratio=crop_bottom_ratio,
        )

        if raw_text:
            with st.expander(f"OCR生テキスト（{platform} / 全体範囲）", expanded=False):
                st.text(raw_text)

        st.info(
            f"[{platform}] OCR切り抜き範囲: "
            f"left={crop_left_ratio:.3f}, top={crop_top_ratio:.3f}, "
            f"right={crop_right_ratio:.3f}, bottom={crop_bottom_ratio:.3f}"
        )

        smart = self._ocr_smartvault_metrics(file_bytes, self._get_smartvault_boxes(settings_df, project, platform))

        st.markdown(f"#### SmartVault {platform.upper()} OCR結果")
        st.image(smart["boxed_preview"], caption=f"赤枠 = {platform} OCR対象範囲", width=500)

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
    # OCR Transaction History Sheet
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

        current = [str(c).strip() for c in first]
        if current != self.OCR_TX_HISTORY_HEADERS:
            merged = current[:]
            for h in self.OCR_TX_HISTORY_HEADERS:
                if h not in merged:
                    merged.append(h)
            ws.update("1:1", [merged])

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
    # Transaction OCR 設計
    # =========================================================
    def _get_tx_layout(self, platform: str) -> Dict[str, float]:
        if platform == "mobile":
            return {
                "base_top": self.MOBILE_TX_SCAN_BASE_TOP_RATIO,
                "step": self.MOBILE_TX_SCAN_STEP_RATIO,
                "max_rows": self.MOBILE_TX_SCAN_MAX_ROWS,
                "date_left": self.MOBILE_TX_DATE_LEFT,
                "date_right": self.MOBILE_TX_DATE_RIGHT,
                "date_top_offset": self.MOBILE_TX_DATE_TOP_OFFSET,
                "date_bottom_offset": self.MOBILE_TX_DATE_BOTTOM_OFFSET,
                "type_left": self.MOBILE_TX_TYPE_LEFT,
                "type_right": self.MOBILE_TX_TYPE_RIGHT,
                "type_top_offset": self.MOBILE_TX_TYPE_TOP_OFFSET,
                "type_bottom_offset": self.MOBILE_TX_TYPE_BOTTOM_OFFSET,
                "usd_left": self.MOBILE_TX_USD_LEFT,
                "usd_right": self.MOBILE_TX_USD_RIGHT,
                "usd_top_offset": self.MOBILE_TX_USD_TOP_OFFSET,
                "usd_bottom_offset": self.MOBILE_TX_USD_BOTTOM_OFFSET,
            }

        return {
            "base_top": self.PC_TX_SCAN_BASE_TOP_RATIO,
            "step": self.PC_TX_SCAN_STEP_RATIO,
            "max_rows": self.PC_TX_SCAN_MAX_ROWS,
            "date_left": self.PC_TX_DATE_LEFT,
            "date_right": self.PC_TX_DATE_RIGHT,
            "date_top_offset": self.PC_TX_DATE_TOP_OFFSET,
            "date_bottom_offset": self.PC_TX_DATE_BOTTOM_OFFSET,
            "type_left": self.PC_TX_TYPE_LEFT,
            "type_right": self.PC_TX_TYPE_RIGHT,
            "type_top_offset": self.PC_TX_TYPE_TOP_OFFSET,
            "type_bottom_offset": self.PC_TX_TYPE_BOTTOM_OFFSET,
            "usd_left": self.PC_TX_USD_LEFT,
            "usd_right": self.PC_TX_USD_RIGHT,
            "usd_top_offset": self.PC_TX_USD_TOP_OFFSET,
            "usd_bottom_offset": self.PC_TX_USD_BOTTOM_OFFSET,
        }

    def _ocr_transaction_rows_by_platform(self, file_bytes: bytes, platform: str) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        layout = self._get_tx_layout(platform)

        for i in range(int(layout["max_rows"])):
            row_top = self._row_top_ratio(float(layout["base_top"]), float(layout["step"]), i)

            date_box = self._build_region_box(
                row_top,
                float(layout["date_left"]),
                float(layout["date_right"]),
                float(layout["date_top_offset"]),
                float(layout["date_bottom_offset"]),
            )
            type_box = self._build_region_box(
                row_top,
                float(layout["type_left"]),
                float(layout["type_right"]),
                float(layout["type_top_offset"]),
                float(layout["type_bottom_offset"]),
            )
            usd_box = self._build_region_box(
                row_top,
                float(layout["usd_left"]),
                float(layout["usd_right"]),
                float(layout["usd_top_offset"]),
                float(layout["usd_bottom_offset"]),
            )

            date_text = self._normalize_ocr_text(self._ocr_crop_text(file_bytes, date_box))
            type_text = self._normalize_ocr_text(self._ocr_crop_text(file_bytes, type_box))
            usd_text = self._normalize_ocr_text(self._ocr_crop_text(file_bytes, usd_box))

            with st.expander(f"{platform} 行{i + 1} OCR結果", expanded=False):
                st.write({"row_top": round(row_top, 4), "date_box": date_box, "type_box": type_box, "usd_box": usd_box})
                st.write({"date_text": date_text or "(empty)"})
                st.write({"type_text": type_text or "(empty)"})
                st.write({"usd_text": usd_text or "(empty)"})

            joined_raw = "\n".join([date_text, type_text, usd_text]).strip()
            if not joined_raw:
                continue

            date_label = self._extract_date_label(date_text or joined_raw)
            time_label = self._extract_time_label(date_text or joined_raw)
            type_label = self._extract_type_label(type_text or joined_raw)
            amount_usd = self._extract_amount_usd(usd_text or joined_raw)

            if amount_usd is None or amount_usd <= 0:
                continue
            if not date_label or not time_label or not type_label:
                continue

            # Mobile は「受け取ったUSDC」だけを対象にする
            if platform == "mobile" and type_label != "受け取ったUSDC":
                continue
            # PC は承認行だけ除外
            if platform == "pc" and type_label == "承認":
                continue

            unique_key = self._make_tx_block_key(date_label, time_label, type_label, amount_usd, platform)

            rows.append(
                {
                    "row_index": i + 1,
                    "date_label": date_label,
                    "time_label": time_label,
                    "type_label": type_label,
                    "amount_usd": float(amount_usd),
                    "token_amount": None,
                    "token_symbol": "",
                    "unique_key": unique_key,
                    "platform": platform,
                    "raw_text": joined_raw,
                }
            )

        return rows

    def _process_transaction_ocr_by_platform(
        self,
        file_bytes: bytes,
        source_image: str,
        source_project: str,
        platform: str,
    ) -> None:
        tx_rows = self._ocr_transaction_rows_by_platform(file_bytes, platform)
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
                        platform,
                        row["raw_text"],
                        created_at,
                    ]
                )

            view_rows.append(
                {
                    "Platform": platform,
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

        st.markdown(f"#### {platform.upper()} OCR結果")
        st.dataframe(pd.DataFrame(view_rows), use_container_width=True, hide_index=True)

        c1, c2, c3 = st.columns(3)
        c1.metric("検出合計USD", U.fmt_usd(total_detected))
        c2.metric("新規追加USD", U.fmt_usd(total_new))
        c3.metric("重複件数", str(duplicate_count))

        if new_sheet_rows:
            st.success(f"{len(new_sheet_rows)}件を {self.OCR_TX_HISTORY_SHEET} に保存しました。")
        else:
            st.info("新規追加はありません。すべて重複として除外しました。")

    # =========================================================
    # UI
    # =========================================================
    def _render_ocr_section(
        self,
        settings_df: pd.DataFrame,
        project: str,
        image_files: List[Path],
        selected_evidence_name: str,
        selected_evidence_bytes: Optional[bytes],
    ) -> None:
        platform = self._detect_platform(selected_evidence_bytes)
        st.caption(f"現在のプラットフォーム判定: {platform}")

        if selected_evidence_bytes:
            self._render_platform_layout_info(platform)

        st.divider()
        st.markdown("#### 取引OCR集計（重複防止）")
        st.caption(f"保存先シート: {self.OCR_TX_HISTORY_SHEET}")

        c_tx1, c_tx2 = st.columns(2)

        with c_tx1:
            if st.button(f"現在の画像から {platform.upper()} OCR集計", use_container_width=True, key="ocr_tx_current_platform"):
                if selected_evidence_bytes:
                    self._process_transaction_ocr_by_platform(
                        selected_evidence_bytes,
                        selected_evidence_name or "selected_image",
                        project,
                        platform,
                    )
                else:
                    st.warning("先にフォルダ画像を選ぶか、画像をアップロードしてください。")

        with c_tx2:
            if st.button("最新画像からOCR集計", use_container_width=True, key="ocr_tx_latest_platform"):
                if image_files:
                    latest_file = image_files[0]
                    try:
                        file_bytes = latest_file.read_bytes()
                        latest_platform = self._detect_platform(file_bytes)
                        st.session_state["apr_folder_selected_name"] = latest_file.name
                        st.session_state["apr_folder_selected_bytes"] = file_bytes
                        self._process_transaction_ocr_by_platform(file_bytes, latest_file.name, project, latest_platform)
                    except Exception as e:
                        st.error(f"最新画像OCRでエラー: {e}")
                else:
                    st.warning("監視フォルダに画像がありません。")

        st.divider()
        st.markdown("#### SmartVault OCR")
        c_sv1, c_sv2 = st.columns(2)

        with c_sv1:
            if st.button("現在の画像から SmartVault OCR", use_container_width=True, key="sv_ocr_current"):
                if selected_evidence_bytes:
                    self._apply_platform_ocr_result(selected_evidence_bytes, settings_df, project, platform)
                else:
                    st.warning("先にフォルダ画像を選ぶか、画像をアップロードしてください。")

        with c_sv2:
            if st.button("最新画像から SmartVault OCR", use_container_width=True, key="sv_ocr_latest"):
                if image_files:
                    latest_file = image_files[0]
                    try:
                        file_bytes = latest_file.read_bytes()
                        latest_platform = self._detect_platform(file_bytes)
                        st.session_state["apr_folder_selected_name"] = latest_file.name
                        st.session_state["apr_folder_selected_bytes"] = file_bytes
                        self._apply_platform_ocr_result(file_bytes, settings_df, project, latest_platform)
                    except Exception as e:
                        st.error(f"最新画像SmartVault OCRでエラー: {e}")
                else:
                    st.warning("監視フォルダに画像がありません。")

    def _render_platform_layout_info(self, platform: str) -> None:
        layout = self._get_tx_layout(platform)
        st.markdown(
            f"""
現在の {platform.upper()} OCR座標
- BaseTop : {float(layout["base_top"]):.3f}
- Step    : {float(layout["step"]):.3f}
- MaxRows : {int(layout["max_rows"])}

日付+時間領域
- Left  : {float(layout["date_left"]):.3f}
- Right : {float(layout["date_right"]):.3f}

種別領域
- Left  : {float(layout["type_left"]):.3f}
- Right : {float(layout["type_right"]):.3f}

USD領域
- Left  : {float(layout["usd_left"]):.3f}
- Right : {float(layout["usd_right"]):.3f}
"""
        )

    # =========================================================
    # Main Render
    # =========================================================
    def _get_default_watch_folder(self) -> str:
        try:
            return str(st.secrets.get("local_paths", {}).get("apr_watch_folder", "")).strip()
        except Exception:
            return ""

    def _folder_image_files(self, folder_path: str) -> List[Path]:
        path = Path(folder_path).expanduser()
        if not path.exists() or not path.is_dir():
            return []

        exts = {".png", ".jpg", ".jpeg", ".webp"}
        files = [p for p in path.iterdir() if p.is_file() and p.suffix.lower() in exts]
        files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return files

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
                if st.button("最新画像を選択", use_container_width=True, key="apr_pick_latest"):
                    latest_file = image_files[0]
                    try:
                        file_bytes = latest_file.read_bytes()
                        st.session_state["apr_folder_selected_name"] = latest_file.name
                        st.session_state["apr_folder_selected_bytes"] = file_bytes
                        st.rerun()
                    except Exception as e:
                        st.error(f"最新画像選択でエラー: {e}")

            with c_folder2:
                if st.button("選択画像を反映", use_container_width=True, key="apr_pick_selected"):
                    if selected_folder_file is None:
                        st.warning("画像を選択してください。")
                    else:
                        try:
                            file_bytes = selected_folder_file.read_bytes()
                            st.session_state["apr_folder_selected_name"] = selected_folder_file.name
                            st.session_state["apr_folder_selected_bytes"] = file_bytes
                            st.rerun()
                        except Exception as e:
                            st.error(f"選択画像反映でエラー: {e}")

            if selected_folder_file is not None:
                try:
                    preview_bytes = selected_folder_file.read_bytes()
                    st.image(preview_bytes, caption=f"フォルダ画像プレビュー: {selected_folder_file.name}", width=500)
                except Exception:
                    pass

        st.markdown("#### 手動アップロード")
        uploaded = st.file_uploader("エビデンス画像（任意）", type=["png", "jpg", "jpeg"], key="apr_img")

        if uploaded is not None and st.button("アップロード画像を反映", key="apr_uploaded_pick"):
            file_bytes = uploaded.getvalue()
            st.session_state["apr_folder_selected_name"] = uploaded.name
            st.session_state["apr_folder_selected_bytes"] = file_bytes
            st.rerun()

        selected_evidence_name = st.session_state.get("apr_folder_selected_name", "")
        selected_evidence_bytes = st.session_state.get("apr_folder_selected_bytes")

        if selected_evidence_name:
            st.caption(f"現在のエビデンス画像: {selected_evidence_name}")

        self._render_ocr_section(settings_df, project, image_files, selected_evidence_name, selected_evidence_bytes)

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
                apr_ledger_count = 0
                line_log_count = 0
                success = 0
                fail = 0
                skip_count = 0
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

                        self.repo.append_ledger(
                            ts, p, person, AppConfig.TYPE["APR"], daily_apr, note, evidence_url or "", uid, disp
                        )
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
                            code = 0
                            line_note = "LINE未送信: Line_User_IDなし"
                        else:
                            code = ExternalService.send_line_push(token, uid, personalized_msg, evidence_url)
                            line_note = (
                                f"HTTP:{code}, "
                                f"Liquidity:{total_liquidity}, "
                                f"YesterdayProfit:{yesterday_profit}, "
                                f"APR:{apr}%, SourceMode:{source_mode}, CompoundTiming:{compound_timing}"
                            )

                        self.repo.append_ledger(
                            ts, p, person, AppConfig.TYPE["LINE"], 0, line_note, evidence_url or "", uid, disp
                        )
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
