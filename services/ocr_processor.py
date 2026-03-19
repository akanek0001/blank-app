from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import re

import pandas as pd

from config import AppConfig
from core.utils import U
from services.external_service import ExternalService


@dataclass(frozen=True)
class OCRBox:
    left: float
    top: float
    right: float
    bottom: float

    def to_dict(self) -> Dict[str, float]:
        return {
            "left": float(self.left),
            "top": float(self.top),
            "right": float(self.right),
            "bottom": float(self.bottom),
        }


class OCRProcessor:
    # =========================================================
    # Mobile transaction OCR layout
    # =========================================================
    MOBILE_TX_SCAN_BASE_TOP_RATIO = 430 / 2532
    MOBILE_TX_SCAN_STEP_RATIO = 123 / 2532
    MOBILE_TX_SCAN_MAX_ROWS = 10

    MOBILE_TX_DATE_LEFT = 0.02
    MOBILE_TX_DATE_RIGHT = 0.40
    MOBILE_TX_DATE_TOP_OFFSET = 0.00
    MOBILE_TX_DATE_BOTTOM_OFFSET = 0.03

    MOBILE_TX_TYPE_LEFT = 0.08
    MOBILE_TX_TYPE_RIGHT = 0.65
    MOBILE_TX_TYPE_TOP_OFFSET = 0.015
    MOBILE_TX_TYPE_BOTTOM_OFFSET = 0.05

    MOBILE_TX_USD_LEFT = 0.65
    MOBILE_TX_USD_RIGHT = 0.93
    MOBILE_TX_USD_TOP_OFFSET = 0.01
    MOBILE_TX_USD_BOTTOM_OFFSET = 0.04

    # =========================================================
    # PC transaction OCR layout
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

    @staticmethod
    def detect_platform(file_bytes: Optional[bytes]) -> str:
        if not file_bytes:
            return "mobile"
        try:
            return "mobile" if U.is_mobile_tall_image(file_bytes) else "pc"
        except Exception:
            return "mobile"

    @staticmethod
    def get_setting_row(settings_df: pd.DataFrame, project: str) -> Optional[pd.Series]:
        try:
            rows = settings_df[
                settings_df["Project_Name"].astype(str).str.strip() == str(project).strip()
            ]
            if rows.empty:
                return None
            return rows.iloc[0]
        except Exception:
            return None

    @classmethod
    def get_general_crop_ratios(
        cls,
        settings_df: pd.DataFrame,
        project: str,
        platform: str,
    ):
        srow = cls.get_setting_row(settings_df, project)
        if srow is None:
            raise ValueError(f"Settings にプロジェクト '{project}' の設定行がありません。")

        if platform == "mobile":
            defaults = {"left": 0.03, "top": 0.14, "right": 0.97, "bottom": 0.92}
            return (
                U.to_ratio(srow.get("Crop_Left_Ratio_Mobile", defaults["left"]), defaults["left"]),
                U.to_ratio(srow.get("Crop_Top_Ratio_Mobile", defaults["top"]), defaults["top"]),
                U.to_ratio(srow.get("Crop_Right_Ratio_Mobile", defaults["right"]), defaults["right"]),
                U.to_ratio(srow.get("Crop_Bottom_Ratio_Mobile", defaults["bottom"]), defaults["bottom"]),
            )

        defaults = {"left": 0.05, "top": 0.18, "right": 0.95, "bottom": 0.88}
        return (
            U.to_ratio(srow.get("Crop_Left_Ratio_PC", defaults["left"]), defaults["left"]),
            U.to_ratio(srow.get("Crop_Top_Ratio_PC", defaults["top"]), defaults["top"]),
            U.to_ratio(srow.get("Crop_Right_Ratio_PC", defaults["right"]), defaults["right"]),
            U.to_ratio(srow.get("Crop_Bottom_Ratio_PC", defaults["bottom"]), defaults["bottom"]),
        )

    @classmethod
    def get_smartvault_boxes(
        cls,
        settings_df: pd.DataFrame,
        project: str,
        platform: str,
    ) -> Dict[str, OCRBox]:
        srow = cls.get_setting_row(settings_df, project)

        if platform == "mobile":
            boxes = AppConfig.SMARTVAULT_BOXES_MOBILE
            return {
                "TOTAL_LIQUIDITY": OCRBox(
                    left=float(boxes["TOTAL_LIQUIDITY"]["left"]),
                    top=float(boxes["TOTAL_LIQUIDITY"]["top"]),
                    right=float(boxes["TOTAL_LIQUIDITY"]["right"]),
                    bottom=float(boxes["TOTAL_LIQUIDITY"]["bottom"]),
                ),
                "YESTERDAY_PROFIT": OCRBox(
                    left=float(boxes["YESTERDAY_PROFIT"]["left"]),
                    top=float(boxes["YESTERDAY_PROFIT"]["top"]),
                    right=float(boxes["YESTERDAY_PROFIT"]["right"]),
                    bottom=float(boxes["YESTERDAY_PROFIT"]["bottom"]),
                ),
                "APR": OCRBox(
                    left=float(boxes["APR"]["left"]),
                    top=float(boxes["APR"]["top"]),
                    right=float(boxes["APR"]["right"]),
                    bottom=float(boxes["APR"]["bottom"]),
                ),
            }

        if srow is None:
            raise ValueError(f"Settings にプロジェクト '{project}' の設定行がありません。")

        required_cols = [
            "SV_Total_Liquidity_Left_PC",
            "SV_Total_Liquidity_Top_PC",
            "SV_Total_Liquidity_Right_PC",
            "SV_Total_Liquidity_Bottom_PC",
            "SV_Yesterday_Profit_Left_PC",
            "SV_Yesterday_Profit_Top_PC",
            "SV_Yesterday_Profit_Right_PC",
            "SV_Yesterday_Profit_Bottom_PC",
            "SV_APR_Left_PC",
            "SV_APR_Top_PC",
            "SV_APR_Right_PC",
            "SV_APR_Bottom_PC",
        ]

        missing = [c for c in required_cols if c not in srow.index]
        if missing:
            raise ValueError(
                f"Settings に PC 用 SmartVault 座標列がありません: {', '.join(missing)}"
            )

        values = {c: str(srow.get(c, "")).strip() for c in required_cols}
        empty = [k for k, v in values.items() if v == ""]
        if empty:
            raise ValueError(
                f"Settings の PC 用 SmartVault 座標が未入力です: {', '.join(empty)}"
            )

        return {
            "TOTAL_LIQUIDITY": OCRBox(
                left=float(values["SV_Total_Liquidity_Left_PC"]),
                top=float(values["SV_Total_Liquidity_Top_PC"]),
                right=float(values["SV_Total_Liquidity_Right_PC"]),
                bottom=float(values["SV_Total_Liquidity_Bottom_PC"]),
            ),
            "YESTERDAY_PROFIT": OCRBox(
                left=float(values["SV_Yesterday_Profit_Left_PC"]),
                top=float(values["SV_Yesterday_Profit_Top_PC"]),
                right=float(values["SV_Yesterday_Profit_Right_PC"]),
                bottom=float(values["SV_Yesterday_Profit_Bottom_PC"]),
            ),
            "APR": OCRBox(
                left=float(values["SV_APR_Left_PC"]),
                top=float(values["SV_APR_Top_PC"]),
                right=float(values["SV_APR_Right_PC"]),
                bottom=float(values["SV_APR_Bottom_PC"]),
            ),
        }

    @staticmethod
    def normalize_text(text: str) -> str:
        t = str(text or "")
        t = t.replace("月 ", "月")
        t = t.replace(" 日", "日")
        t = t.replace(" at ", " ")
        t = t.replace("午前", "am")
        t = t.replace("午後", "pm")
        t = re.sub(r"[ \t\u3000]+", " ", t)
        return t.strip()

    @staticmethod
    def ocr_crop_text(file_bytes: bytes, box: OCRBox) -> str:
        return ExternalService.ocr_space_extract_text_with_crop(
            file_bytes=file_bytes,
            crop_left_ratio=box.left,
            crop_top_ratio=box.top,
            crop_right_ratio=box.right,
            crop_bottom_ratio=box.bottom,
        )

    @staticmethod
    def row_top_ratio(base_top: float, step: float, row_index: int) -> float:
        return base_top + (step * row_index)

    @staticmethod
    def build_region_box(
        row_top: float,
        left_ratio: float,
        right_ratio: float,
        top_offset_ratio: float,
        bottom_offset_ratio: float,
    ) -> OCRBox:
        return OCRBox(
            left=float(left_ratio),
            top=float(row_top + top_offset_ratio),
            right=float(right_ratio),
            bottom=float(row_top + bottom_offset_ratio),
        )

    @classmethod
    def extract_metrics(cls, file_bytes: bytes, boxes: Dict[str, OCRBox]) -> Dict[str, Any]:
        total_text = cls.ocr_crop_text(file_bytes, boxes["TOTAL_LIQUIDITY"])
        profit_text = cls.ocr_crop_text(file_bytes, boxes["YESTERDAY_PROFIT"])
        apr_text = cls.ocr_crop_text(file_bytes, boxes["APR"])

        total_vals = U.extract_usd_candidates(total_text)
        profit_vals = U.extract_usd_candidates(profit_text)
        apr_vals = U.extract_percent_candidates(apr_text)

        total_liquidity = U.pick_total_liquidity(total_vals)
        yesterday_profit = U.pick_yesterday_profit(profit_vals)
        apr_value = apr_vals[0] if apr_vals else None

        boxed_preview = U.draw_ocr_boxes(file_bytes, {k: v.to_dict() for k, v in boxes.items()})

        return {
            "total_liquidity": total_liquidity,
            "yesterday_profit": yesterday_profit,
            "apr_value": apr_value,
            "preview": boxed_preview,
            "total_text": total_text,
            "profit_text": profit_text,
            "apr_text": apr_text,
            "boxes": {k: v.to_dict() for k, v in boxes.items()},
        }

    @classmethod
    def get_tx_layout(cls, platform: str) -> Dict[str, float]:
        if platform == "mobile":
            return {
                "base_top": cls.MOBILE_TX_SCAN_BASE_TOP_RATIO,
                "step": cls.MOBILE_TX_SCAN_STEP_RATIO,
                "max_rows": cls.MOBILE_TX_SCAN_MAX_ROWS,
                "date_left": cls.MOBILE_TX_DATE_LEFT,
                "date_right": cls.MOBILE_TX_DATE_RIGHT,
                "date_top_offset": cls.MOBILE_TX_DATE_TOP_OFFSET,
                "date_bottom_offset": cls.MOBILE_TX_DATE_BOTTOM_OFFSET,
                "type_left": cls.MOBILE_TX_TYPE_LEFT,
                "type_right": cls.MOBILE_TX_TYPE_RIGHT,
                "type_top_offset": cls.MOBILE_TX_TYPE_TOP_OFFSET,
                "type_bottom_offset": cls.MOBILE_TX_TYPE_BOTTOM_OFFSET,
                "usd_left": cls.MOBILE_TX_USD_LEFT,
                "usd_right": cls.MOBILE_TX_USD_RIGHT,
                "usd_top_offset": cls.MOBILE_TX_USD_TOP_OFFSET,
                "usd_bottom_offset": cls.MOBILE_TX_USD_BOTTOM_OFFSET,
            }

        return {
            "base_top": cls.PC_TX_SCAN_BASE_TOP_RATIO,
            "step": cls.PC_TX_SCAN_STEP_RATIO,
            "max_rows": cls.PC_TX_SCAN_MAX_ROWS,
            "date_left": cls.PC_TX_DATE_LEFT,
            "date_right": cls.PC_TX_DATE_RIGHT,
            "date_top_offset": cls.PC_TX_DATE_TOP_OFFSET,
            "date_bottom_offset": cls.PC_TX_DATE_BOTTOM_OFFSET,
            "type_left": cls.PC_TX_TYPE_LEFT,
            "type_right": cls.PC_TX_TYPE_RIGHT,
            "type_top_offset": cls.PC_TX_TYPE_TOP_OFFSET,
            "type_bottom_offset": cls.PC_TX_TYPE_BOTTOM_OFFSET,
            "usd_left": cls.PC_TX_USD_LEFT,
            "usd_right": cls.PC_TX_USD_RIGHT,
            "usd_top_offset": cls.PC_TX_USD_TOP_OFFSET,
            "usd_bottom_offset": cls.PC_TX_USD_BOTTOM_OFFSET,
        }

    @classmethod
    def extract_date(cls, text: str) -> str:
        t = cls.normalize_text(text)
        patterns = [
            r"(\d{1,2}\s*月\s*\d{1,2}\s*日)",
            r"(\d{1,2}/\d{1,2})",
            r"(\d{1,2}-\d{1,2})",
        ]
        for p in patterns:
            m = re.search(p, t)
            if m:
                return cls.normalize_text(m.group(1)).replace(" ", "")
        return ""

    @classmethod
    def extract_time(cls, text: str) -> str:
        t = cls.normalize_text(text)
        patterns = [
            r"(\d{1,2}:\d{2}\s*(?:am|pm|AM|PM))",
            r"(\d{1,2}:\d{2})",
        ]
        for p in patterns:
            m = re.search(p, t)
            if m:
                return cls.normalize_text(m.group(1)).lower()
        return ""

    @classmethod
    def extract_type_label(cls, text: str) -> str:
        t = cls.normalize_text(text)
        if "受け取ったUSDC" in t or "受け取った USDC" in t:
            return "受け取ったUSDC"
        if "トークンを受け取りました" in t:
            return "トークンを受け取りました"
        if "承認" in t:
            return "承認"
        if "USDC" in t:
            return "USDC"
        return ""

    @classmethod
    def extract_amount(cls, text: str) -> Optional[float]:
        t = cls.normalize_text(text)
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

    @staticmethod
    def make_unique_key(date_label: str, time_label: str, type_label: str, amount: float, platform: str) -> str:
        return f"{platform}|{date_label}|{time_label}|{type_label}|{amount:.2f}"

    @classmethod
    def extract_transaction_rows(cls, file_bytes: bytes, platform: str) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        layout = cls.get_tx_layout(platform)

        for i in range(int(layout["max_rows"])):
            row_top = cls.row_top_ratio(float(layout["base_top"]), float(layout["step"]), i)

            date_box = cls.build_region_box(
                row_top,
                layout["date_left"],
                layout["date_right"],
                layout["date_top_offset"],
                layout["date_bottom_offset"],
            )
            type_box = cls.build_region_box(
                row_top,
                layout["type_left"],
                layout["type_right"],
                layout["type_top_offset"],
                layout["type_bottom_offset"],
            )
            usd_box = cls.build_region_box(
                row_top,
                layout["usd_left"],
                layout["usd_right"],
                layout["usd_top_offset"],
                layout["usd_bottom_offset"],
            )

            date_text = cls.normalize_text(cls.ocr_crop_text(file_bytes, date_box))
            type_text = cls.normalize_text(cls.ocr_crop_text(file_bytes, type_box))
            usd_text = cls.normalize_text(cls.ocr_crop_text(file_bytes, usd_box))

            joined_raw = "\n".join([date_text, type_text, usd_text]).strip()
            if not joined_raw:
                continue

            date_label = cls.extract_date(date_text or joined_raw)
            time_label = cls.extract_time(date_text or joined_raw)
            type_label = cls.extract_type_label(type_text or joined_raw)
            amount_usd = cls.extract_amount(usd_text or joined_raw)

            if amount_usd is None or amount_usd <= 0:
                continue
            if not date_label or not time_label or not type_label:
                continue
            if platform == "mobile" and type_label != "受け取ったUSDC":
                continue
            if platform == "pc" and type_label == "承認":
                continue

            unique_key = cls.make_unique_key(date_label, time_label, type_label, amount_usd, platform)

            rows.append(
                {
                    "row_index": i + 1,
                    "date_label": date_label,
                    "time_label": time_label,
                    "type_label": type_label,
                    "amount_usd": float(amount_usd),
                    "unique_key": unique_key,
                    "platform": platform,
                    "raw_text": joined_raw,
                    "date_box": date_box.to_dict(),
                    "type_box": type_box.to_dict(),
                    "usd_box": usd_box.to_dict(),
                    "date_text": date_text,
                    "type_text": type_text,
                    "usd_text": usd_text,
                }
            )

        return rows
