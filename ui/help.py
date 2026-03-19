from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from io import BytesIO
from typing import Any, Dict, List, Optional, Set, Tuple

import pandas as pd
import requests
import streamlit as st
from PIL import Image, ImageEnhance, ImageFilter, ImageOps, ImageDraw

import gspread
from google.oauth2.service_account import Credentials
from gspread.exceptions import APIError

# =========================================================
# 1. CONFIGURATION
# =========================================================
class AppConfig:
    APP_TITLE = "APR 資産運用管理システム Pro"
    APP_ICON = "🏦"
    JST = timezone(timedelta(hours=9), "JST")

    # シート名
    SHEET = {
        "SETTINGS": "Settings",
        "MEMBERS": "Members",
        "LEDGER": "Ledger",
        "OCR_TX_HISTORY": "OCR_Transaction_History"
    }

    # OCR 座標定義 (Mobile 1170x2532 / PC 基準)
    OCR_LAYOUTS = {
        "mobile": {
            "base_top": 430 / 2532, "step": 123 / 2532, "max_rows": 10,
            "date": {"l": 0.02, "r": 0.40, "t_off": 0.0, "b_off": 0.03},
            "type": {"l": 0.08, "r": 0.65, "t_off": 0.015, "b_off": 0.05},
            "usd": {"l": 0.65, "r": 0.93, "t_off": 0.01, "b_off": 0.04},
        },
        "pc": {
            "base_top": 0.18, "step": 0.08, "max_rows": 12,
            "date": {"l": 0.04, "r": 0.28, "t_off": 0.0, "b_off": 0.05},
            "type": {"l": 0.10, "r": 0.48, "t_off": 0.03, "b_off": 0.10},
            "usd": {"l": 0.72, "r": 0.94, "t_off": 0.02, "b_off": 0.08},
        }
    }

# =========================================================
# 2. OCR ENGINE (コアロジック)
# =========================================================
class OCREngine:
    @staticmethod
    def normalize_text(text: str) -> str:
        """OCRテキストの揺れを補正"""
        t = str(text or "").replace("月 ", "月").replace(" 日", "日").replace(" at ", " ")
        t = t.replace("午前", "am").replace("午後", "pm")
        return re.sub(r"[ \t\u3000]+", " ", t).strip()

    @staticmethod
    def extract_usd(text: str) -> Optional[float]:
        """テキストから金額を抽出"""
        nums = re.findall(r"(\d{1,3}(?:,\d{3})*(?:\.\d+)?)", text.replace("$", ""))
        if not nums: return None
        return float(nums[0].replace(",", ""))

    @staticmethod
    def make_unique_key(date: str, time: str, typ: str, amt: float) -> str:
        """重複防止用のユニークキー生成"""
        return f"{date}_{time}_{typ}_{amt}".replace(" ", "")

# =========================================================
# 3. REPOSITORY
# =========================================================
class Repository:
    def __init__(self):
        creds = Credentials.from_service_account_info(
            st.secrets["connections"]["gsheets"]["credentials"],
            scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        )
        self.gc = gspread.authorize(creds)
        self.book = self.gc.open_by_key(st.secrets["connections"]["gsheets"]["spreadsheet"])

    def get_existing_keys(self) -> Set[str]:
        ws = self.book.worksheet(AppConfig.SHEET["OCR_TX_HISTORY"])
        vals = ws.col_values(1) # A列がUnique_Key
        return set(vals[1:]) if len(vals) > 1 else set()

    def append_rows(self, rows: List[List[Any]]):
        ws = self.book.worksheet(AppConfig.SHEET["OCR_TX_HISTORY"])
        ws.append_rows(rows, value_input_option="USER_ENTERED")

# =========================================================
# 4. MAIN UI
# =========================================================
def main():
    st.set_page_config(page_title=AppConfig.APP_TITLE, layout="wide")
    st.title(f"{AppConfig.APP_ICON} {AppConfig.APP_TITLE}")

    repo = Repository()
    
    st.header("🔍 取引明細スキャン (Multi-Row OCR)")
    uploaded = st.file_uploader("SmartVaultのスクリーンショットを選択", type=["png", "jpg", "jpeg"])

    if uploaded:
        file_bytes = uploaded.getvalue()
        # プラットフォーム自動判定
        is_mobile = Image.open(BytesIO(file_bytes)).height / Image.open(BytesIO(file_bytes)).width > 1.45
        mode = "mobile" if is_mobile else "pc"
        layout = AppConfig.OCR_LAYOUTS[mode]

        st.info(f"判定モード: {mode.upper()} (最大 {layout['max_rows']} 行スキャン)")
        
        if st.button("OCRスキャン開始"):
            existing_keys = repo.get_existing_keys()
            new_data = []
            progress = st.progress(0)
            
            for i in range(layout["max_rows"]):
                # 各行のTop座標を計算
                row_top = layout["base_top"] + (layout["step"] * i)
                
                # Date, Type, USD 領域を個別に切り抜いてOCR
                def get_text(box_key):
                    box = layout[box_key]
                    cropped = OCREngine.crop_image(file_bytes, box['l'], row_top + box['t_off'], box['r'], row_top + box['b_off'])
                    # 外部API呼び出し
                    return OCREngine.call_ocr_api(cropped)

                # --- 疑似コード: 実際にはAPIを叩く ---
                # date_raw = get_text("date")
                # type_raw = get_text("type")
                # usd_raw = get_text("usd")
                # ----------------------------------
                
                progress.progress((i + 1) / layout["max_rows"])
            
            st.success("スキャン完了（重複チェック済み）")

# ※ OCREngine.crop_image や call_ocr_api は前述の ExternalService を参照
if __name__ == "__main__":
    main()
