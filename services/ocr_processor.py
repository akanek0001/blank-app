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
    """
    OCR処理専用
    - SmartVault 3項目 OCR
    - 取引履歴 3領域 OCR
    - Settings シートの値で3領域OCRを調整可能
    """

    # =========================================================
    # Defaults: Mobile transaction OCR
    # 画像 828x1792 基準で調整
    # =========================================================
    DEFAULT_TX_LAYOUT_MOBILE = {
        "base_top": 0.220,
        "step": 0.115,
        "max_rows": 12,
        "date_left": 0.050,
        "date_right": 0.450,
        "date_top_offset": 0.000,
        "date_bottom_offset": 0.030,
        "type_left": 0.180,
        "type_right": 0.700,
        "type_top_offset": 0.015,
        "type_bottom_offset": 0.055,
        "usd_left": 0.720,
        "usd_right": 0.960,
        "usd_top_offset": 0.010,
        "usd_bottom_offset": 0.055,
    }

    # =========================================================
    # Defaults: PC transaction OCR
    # =========================================================
    DEFAULT_TX_LAYOUT_PC = {
        "base_top": 0.18,
        "step": 0.08,
        "max_rows": 12,
        "date_left": 0.04,
        "date_right": 0.28,
        "date_top_offset": 0.00,
        "date_bottom_offset": 0.05,
        "type_left": 0.10,
        "type_right": 0.48,
        "type_top_offset": 0.03,
        "type_bottom_offset": 0.10,
        "usd_left": 0.72,
        "usd_right": 0.94,
        "usd_top_offset": 0.02,
        "usd_bottom_offset": 0.08,
    }

    MOBILE_SETTING_MAP = {
        "base_top": "TX_Scan_BaseTop_Ratio_Mobile",
        "step": "TX_Scan_Step_Ratio_Mobile",
        "max_rows": "TX_Scan_MaxRows_Mobile",
        "date_left": "TX_Date_Left_Ratio_Mobile",
        "date_right": "TX_Date_Right_Ratio_Mobile",
        "date_top_offset": "TX_Date_Top_Offset_Ratio_Mobile",
        "date_bottom_offset": "TX_Date_Bottom_Offset_Ratio_Mobile",
        "type_left": "TX_Type_Left_Ratio_Mobile",
        "type_right": "TX_Type_Right_Ratio_Mobile",
        "type_top_offset": "TX_Type_Top_Offset_Ratio_Mobile",
        "type_bottom_offset": "TX_Type_Bottom_Offset_Ratio_Mobile",
        "usd_left": "TX_USD_Left_Ratio_Mobile",
        "usd_right": "TX_USD_Right_Ratio_Mobile",
        "usd_top_offset": "TX_USD_Top_Offset_Ratio_Mobile",
        "usd_bottom_offset": "TX_USD_Bottom_Offset_Ratio_Mobile",
    }

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

    @staticmethod
    def _to_ratio(value: Any, default: float) -> float:
        try:
            return float(U.to_ratio(value, default))
        except Exception:
            return float(default)

    @staticmethod
    def _to_int(value: Any, default: int) -> int:
        try:
            if value is None:
                return int(default)
            if str(value).strip() == "":
                return int(default)
            return int(float(value))
        except Exception:
            return int(default)

    @classmethod
    def get_tx_layout(
        cls,
        settings_df: pd.DataFrame,
        project: str,
        platform: str,
    ) -> Dict[str, float]:
        if platform != "mobile":
            return dict(cls.DEFAULT_TX_LAYOUT_PC)

        layout = dict(cls.DEFAULT_TX_LAYOUT_MOBILE)
        srow = cls.get_setting_row(settings_df, project)
        if srow is None:
            return layout

        for key, col in cls.MOBILE_SETTING_MAP.items():
            if col not in srow.index:
                continue

            if key == "max_rows":
                layout[key] = cls._to_int(srow.get(col), int(layout[key]))
            else:
                layout[key] = cls._to_ratio(srow.get(col), float(layout[key]))

        return layout

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
            defaults = {
                "left": AppConfig.OCR_DEFAULTS_MOBILE["Crop_Left_Ratio_Mobile"],
                "top": AppConfig.OCR_DEFAULTS_MOBILE["Crop_Top_Ratio_Mobile"],
                "right": AppConfig.OCR_DEFAULTS_MOBILE["Crop_Right_Ratio_Mobile"],
                "bottom": AppConfig.OCR_DEFAULTS_MOBILE["Crop_Bottom_Ratio_Mobile"],
            }
            return (
                cls._to_ratio(srow.get("Crop_Left_Ratio_Mobile"), defaults["left"]),
                cls._to_ratio(srow.get("Crop_Top_Ratio_Mobile"), defaults["top"]),
                cls._to_ratio(srow.get("Crop_Right_Ratio_Mobile"), defaults["right"]),
                cls._to_ratio(srow.get("Crop_Bottom_Ratio_Mobile"), defaults["bottom"]),
            )

        defaults = {
            "left": AppConfig.OCR_DEFAULTS_PC["Crop_Left_Ratio_PC"],
            "top": AppConfig.OCR_DEFAULTS_PC["Crop_Top_Ratio_PC"],
            "right": AppConfig.OCR_DEFAULTS_PC["Crop_Right_Ratio_PC"],
            "bottom": AppConfig.OCR_DEFAULTS_PC["Crop_Bottom_Ratio_PC"],
        }
        return (
            cls._to_ratio(srow.get("Crop_Left_Ratio_PC"), defaults["left"]),
            cls._to_ratio(srow.get("Crop_Top_Ratio_PC"), defaults["top"]),
            cls._to_ratio(srow.get("Crop_Right_Ratio_PC"), defaults["right"]),
            cls._to_ratio(srow.get("Crop_Bottom_Ratio_PC"), defaults["bottom"]),
        )

    @classmethod
    def get_smartvault_boxes(
        cls,
        settings_df: pd.DataFrame,
        project: str,
        platform: str,
    ) -> Dict[str, OCRBox]:
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

        srow = cls.get_setting_row(settings_df, project)
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

        boxed_preview = U.draw_ocr_boxes(
            file_bytes,
            {k: v.to_dict() for k, v in boxes.items()},
        )

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
    def make_unique_key(
        date_label: str,
        time_label: str,
        type_label: str,
        amount: float,
        platform: str,
    ) -> str:
        return f"{platform}|{date_label}|{time_label}|{type_label}|{amount:.2f}"

    @classmethod
    def _is_target_transaction(cls, type_label: str, raw_text: str, platform: str) -> bool:
        """
        受け取ったUSDCのみ通す
        """
        t = cls.normalize_text(type_label or raw_text)

        if "受け取ったUSDC" in t or "受け取った USDC" in t:
            return True

        return False

    @classmethod
    def extract_transaction_rows(
        cls,
        file_bytes: bytes,
        settings_df: pd.DataFrame,
        project: str,
        platform: str,
    ) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        layout = cls.get_tx_layout(settings_df, project, platform)

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
            if not date_label or not time_label:
                continue
            if not cls._is_target_transaction(type_label, joined_raw, platform):
                continue

            unique_key = cls.make_unique_key(date_label, time_label, type_label or "受け取ったUSDC", amount_usd, platform)

            rows.append(
                {
                    "row_index": i + 1,
                    "date_label": date_label,
                    "time_label": time_label,
                    "type_label": type_label or "受け取ったUSDC",
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

    @classmethod
    def build_preview_boxes(
        cls,
        settings_df: pd.DataFrame,
        project: str,
        platform: str,
        rows_to_show: int = 3,
    ) -> Dict[str, Dict[str, float]]:
        layout = cls.get_tx_layout(settings_df, project, platform)
        out: Dict[str, Dict[str, float]] = {}

        max_rows = max(1, min(int(layout["max_rows"]), int(rows_to_show)))

        for i in range(max_rows):
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

            row_no = i + 1
            out[f"ROW{row_no}_DATE"] = date_box.to_dict()
            out[f"ROW{row_no}_TYPE"] = type_box.to_dict()
            out[f"ROW{row_no}_USD"] = usd_box.to_dict()

        return out
