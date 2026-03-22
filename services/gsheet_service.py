from __future__ import annotations

from typing import Any

import gspread
import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials


class GSheetService:
    def __init__(self, spreadsheet_id: str):
        self.spreadsheet_id = self._resolve_spreadsheet_id(spreadsheet_id)
        self.gc = self._connect()
        self.sh = self.gc.open_by_key(self.spreadsheet_id)
        if "gsheet_cache" not in st.session_state:
            st.session_state["gsheet_cache"] = {}

    def _resolve_spreadsheet_id(self, spreadsheet_id: str) -> str:
        raw = str(spreadsheet_id or "").strip()
        if raw and raw != "YOUR_SPREADSHEET_ID":
            return raw.split('/d/')[1].split('/')[0] if '/d/' in raw else raw
        try:
            sid = str(st.secrets["connections"]["gsheets"]["spreadsheet"]).strip()
            if sid:
                return sid.split('/d/')[1].split('/')[0] if '/d/' in sid else sid
        except Exception:
            pass
        raise KeyError("Spreadsheet ID が見つかりません。")

    def _connect(self):
        try:
            creds_dict = dict(st.secrets["connections"]["gsheets"]["credentials"])
        except Exception:
            creds_dict = dict(st.secrets["gcp_service_account"])
        creds = Credentials.from_service_account_info(
            creds_dict,
            scopes=[
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive",
            ],
        )
        return gspread.authorize(creds)

    def clear_cache(self):
        st.session_state["gsheet_cache"] = {}

    def worksheet(self, sheet_name: str):
        return self.sh.worksheet(sheet_name)

    def ensure_sheet(self, sheet_name: str, headers: list[str]) -> None:
        try:
            ws = self.worksheet(sheet_name)
        except gspread.exceptions.WorksheetNotFound:
            ws = self.sh.add_worksheet(title=sheet_name, rows=2000, cols=max(20, len(headers)))
            ws.append_row(headers, value_input_option="USER_ENTERED")
            return
        values = ws.get_all_values()
        if not values:
            ws.append_row(headers, value_input_option="USER_ENTERED")
            return
        current = [str(x).strip() for x in values[0]]
        expected = [str(x).strip() for x in headers]
        if current != expected:
            body = values[1:] if len(values) > 1 else []
            ws.clear()
            ws.append_row(expected, value_input_option="USER_ENTERED")
            if body:
                normalized = []
                for r in body:
                    r = list(r)
                    if len(r) < len(expected):
                        r += [""] * (len(expected) - len(r))
                    normalized.append(r[: len(expected)])
                ws.append_rows(normalized, value_input_option="USER_ENTERED")

    def _read_sheet(self, sheet_name: str) -> pd.DataFrame:
        ws = self.worksheet(sheet_name)
        values = ws.get_all_values()
        if not values:
            return pd.DataFrame()
        headers = values[0]
        rows = values[1:]
        if not rows:
            return pd.DataFrame(columns=headers)
        return pd.DataFrame(rows, columns=headers).loc[:, lambda d: ~d.columns.duplicated()]

    def load_df(self, sheet_name: str) -> pd.DataFrame:
        cache = st.session_state["gsheet_cache"]
        if sheet_name in cache:
            return cache[sheet_name].copy()
        try:
            df = self._read_sheet(sheet_name)
        except gspread.exceptions.WorksheetNotFound:
            df = pd.DataFrame()
        cache[sheet_name] = df.copy()
        return df.copy()

    def write_df(self, sheet_name: str, df: pd.DataFrame):
        try:
            ws = self.worksheet(sheet_name)
        except gspread.exceptions.WorksheetNotFound:
            from config import AppConfig
            mapping = {v:k for k,v in AppConfig.SHEET.items()}
            key = mapping.get(sheet_name)
            headers = AppConfig.HEADERS[key] if key else list(df.columns)
            self.ensure_sheet(sheet_name, headers)
            ws = self.worksheet(sheet_name)
        if df is None or df.empty:
            ws.clear()
            return
        out = df.loc[:, ~df.columns.duplicated()].copy()
        data = [out.columns.tolist()] + out.fillna("").astype(str).values.tolist()
        ws.clear()
        ws.update(data)

    def append_row(self, sheet_name: str, row: list[Any]):
        try:
            ws = self.worksheet(sheet_name)
        except gspread.exceptions.WorksheetNotFound:
            from config import AppConfig
            mapping = {v:k for k,v in AppConfig.SHEET.items()}
            key = mapping.get(sheet_name)
            headers = AppConfig.HEADERS[key] if key else []
            self.ensure_sheet(sheet_name, headers)
            ws = self.worksheet(sheet_name)
        ws.append_row(["" if x is None else x for x in row], value_input_option="USER_ENTERED")
