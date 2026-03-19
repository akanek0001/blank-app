from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Any
import re

import pandas as pd

from core.utils import U
from config import AppConfig
from services.external_service import ExternalService


@dataclass
class OCRBox:
    left: float
    top: float
    right: float
    bottom: float

    def as_dict(self) -> Dict[str, float]:
        return {
            "left": float(self.left),
            "top": float(self.top),
            "right": float(self.right),
            "bottom": float(self.bottom),
        }


class OCRProcessor:
    """
    OCR処理専用クラス
    """

    # =========================================================
    # モバイル3領域OCR設定
    # =========================================================

    TX_SCAN_BASE_TOP_RATIO = 430 / 2532
    TX_SCAN_STEP_RATIO = 123 / 2532
    TX_SCAN_MAX_ROWS = 10

    TX_DATE_LEFT = 0.02
    TX_DATE_RIGHT = 0.40
    TX_DATE_TOP_OFFSET = 0.00
    TX_DATE_BOTTOM_OFFSET = 0.03

    TX_TYPE_LEFT = 0.08
    TX_TYPE_RIGHT = 0.65
    TX_TYPE_TOP_OFFSET = 0.015
    TX_TYPE_BOTTOM_OFFSET = 0.05

    TX_USD_LEFT = 0.65
    TX_USD_RIGHT = 0.93
    TX_USD_TOP_OFFSET = 0.01
    TX_USD_BOTTOM_OFFSET = 0.04

    # =========================================================
    # OCR呼び出し
    # =========================================================

    @staticmethod
    def ocr_crop(file_bytes: bytes, box: OCRBox) -> str:

        return ExternalService.ocr_space_extract_text_with_crop(
            file_bytes=file_bytes,
            crop_left_ratio=box.left,
            crop_top_ratio=box.top,
            crop_right_ratio=box.right,
            crop_bottom_ratio=box.bottom,
        )

    # =========================================================
    # 文字正規化
    # =========================================================

    @staticmethod
    def normalize(text: str) -> str:

        t = str(text or "")

        t = t.replace("月 ", "月")
        t = t.replace(" 日", "日")

        t = t.replace(" at ", " ")

        t = t.replace("午前", "am")
        t = t.replace("午後", "pm")

        t = re.sub(r"[ \t\u3000]+", " ", t)

        return t.strip()

    # =========================================================
    # 行の位置
    # =========================================================

    @classmethod
    def row_top(cls, index: int) -> float:

        return cls.TX_SCAN_BASE_TOP_RATIO + cls.TX_SCAN_STEP_RATIO * index

    # =========================================================
    # OCRボックス作成
    # =========================================================

    @classmethod
    def build_box(
        cls,
        row_top: float,
        left: float,
        right: float,
        top_offset: float,
        bottom_offset: float,
    ) -> OCRBox:

        return OCRBox(
            left=left,
            top=row_top + top_offset,
            right=right,
            bottom=row_top + bottom_offset,
        )

    # =========================================================
    # 日付抽出
    # =========================================================

    @staticmethod
    def extract_date(text: str) -> str:

        t = OCRProcessor.normalize(text)

        patterns = [
            r"(\d{1,2}\s*月\s*\d{1,2}\s*日)",
            r"(\d{1,2}/\d{1,2})",
            r"(\d{1,2}-\d{1,2})",
        ]

        for p in patterns:
            m = re.search(p, t)
            if m:
                return OCRProcessor.normalize(m.group(1)).replace(" ", "")

        return ""

    # =========================================================
    # 時刻抽出
    # =========================================================

    @staticmethod
    def extract_time(text: str) -> str:

        t = OCRProcessor.normalize(text)

        patterns = [
            r"(\d{1,2}:\d{2}\s*(?:am|pm|AM|PM))",
            r"(\d{1,2}:\d{2})",
        ]

        for p in patterns:
            m = re.search(p, t)
            if m:
                return OCRProcessor.normalize(m.group(1)).lower()

        return ""

    # =========================================================
    # 種別
    # =========================================================

    @staticmethod
    def extract_type(text: str) -> str:

        t = OCRProcessor.normalize(text)

        if "受け取ったUSDC" in t:
            return "受け取ったUSDC"

        if "トークンを受け取りました" in t:
            return "トークンを受け取りました"

        if "承認" in t:
            return "承認"

        return ""

    # =========================================================
    # 金額抽出
    # =========================================================

    @staticmethod
    def extract_usd(text: str) -> Optional[float]:

        t = OCRProcessor.normalize(text)

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

    # =========================================================
    # Unique Key
    # =========================================================

    @staticmethod
    def make_key(date_label: str, time_label: str, type_label: str, amount: float) -> str:

        return f"{date_label}|{time_label}|{type_label}|{amount:.2f}"

    # =========================================================
    # 3領域OCR
    # =========================================================

    @classmethod
    def scan_transactions(cls, file_bytes: bytes) -> List[Dict[str, Any]]:

        rows: List[Dict[str, Any]] = []

        for i in range(cls.TX_SCAN_MAX_ROWS):

            row_top = cls.row_top(i)

            date_box = cls.build_box(
                row_top,
                cls.TX_DATE_LEFT,
                cls.TX_DATE_RIGHT,
                cls.TX_DATE_TOP_OFFSET,
                cls.TX_DATE_BOTTOM_OFFSET,
            )

            type_box = cls.build_box(
                row_top,
                cls.TX_TYPE_LEFT,
                cls.TX_TYPE_RIGHT,
                cls.TX_TYPE_TOP_OFFSET,
                cls.TX_TYPE_BOTTOM_OFFSET,
            )

            usd_box = cls.build_box(
                row_top,
                cls.TX_USD_LEFT,
                cls.TX_USD_RIGHT,
                cls.TX_USD_TOP_OFFSET,
                cls.TX_USD_BOTTOM_OFFSET,
            )

            date_text = cls.normalize(cls.ocr_crop(file_bytes, date_box))
            type_text = cls.normalize(cls.ocr_crop(file_bytes, type_box))
            usd_text = cls.normalize(cls.ocr_crop(file_bytes, usd_box))

            raw = "\n".join([date_text, type_text, usd_text]).strip()

            if not raw:
                continue

            date_label = cls.extract_date(date_text or raw)
            time_label = cls.extract_time(date_text or raw)
            type_label = cls.extract_type(type_text or raw)
            amount = cls.extract_usd(usd_text or raw)

            if amount is None or amount <= 0:
                continue

            if not date_label or not time_label or not type_label:
                continue

            if type_label != "受け取ったUSDC":
                continue

            key = cls.make_key(date_label, time_label, type_label, amount)

            rows.append(
                {
                    "row_index": i + 1,
                    "date_label": date_label,
                    "time_label": time_label,
                    "type_label": type_label,
                    "amount_usd": float(amount),
                    "unique_key": key,
                    "raw_text": raw,
                    "date_box": date_box.as_dict(),
                    "type_box": type_box.as_dict(),
                    "usd_box": usd_box.as_dict(),
                }
            )

        return rows
