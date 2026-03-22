from __future__ import annotations

from typing import Optional

import pandas as pd

from config import AppConfig
from services.gsheet_service import GSheetService


class Repository:
    def __init__(self, gs: GSheetService):
        self.gs = gs

    def ensure_all_sheets(self) -> None:
        for key, sheet_name in AppConfig.SHEET.items():
            self.gs.ensure_sheet(sheet_name, AppConfig.HEADERS[key])

    def _ensure_columns(self, df: pd.DataFrame, headers: list[str]) -> pd.DataFrame:
        out = df.copy()
        out = out.loc[:, ~out.columns.duplicated()]
        for col in headers:
            if col not in out.columns:
                out[col] = ""
        return out[headers].copy()

    def _bootstrap_settings_if_empty(self) -> None:
        df = self.gs.load_df(AppConfig.SHEET["SETTINGS"])
        if not df.empty:
            return
        row = {c: "" for c in AppConfig.HEADERS["SETTINGS"]}
        row["Project_Name"] = AppConfig.PROJECT["PERSONAL"]
        row["Net_Factor"] = AppConfig.FACTOR["MASTER"]
        row["IsCompound"] = "TRUE"
        row["Compound_Timing"] = AppConfig.COMPOUND["NONE"]
        row["UpdatedAt_JST"] = pd.Timestamp.now(tz="Asia/Tokyo").strftime("%Y-%m-%d %H:%M:%S")
        row["Active"] = "TRUE"
        self.gs.write_df(AppConfig.SHEET["SETTINGS"], pd.DataFrame([row]))
        self.gs.clear_cache()

    def load_settings(self) -> pd.DataFrame:
        self._bootstrap_settings_if_empty()
        df = self.gs.load_df(AppConfig.SHEET["SETTINGS"])
        if df.empty:
            return pd.DataFrame(columns=AppConfig.HEADERS["SETTINGS"])
        return self._ensure_columns(df, AppConfig.HEADERS["SETTINGS"])

    def write_settings(self, df: pd.DataFrame) -> None:
        self.gs.write_df(AppConfig.SHEET["SETTINGS"], self._ensure_columns(df, AppConfig.HEADERS["SETTINGS"]))
        self.gs.clear_cache()

    def load_members(self) -> pd.DataFrame:
        df = self.gs.load_df(AppConfig.SHEET["MEMBERS"])
        if df.empty:
            return pd.DataFrame(columns=AppConfig.HEADERS["MEMBERS"])
        return self._ensure_columns(df, AppConfig.HEADERS["MEMBERS"])

    def write_members(self, df: pd.DataFrame) -> None:
        self.gs.write_df(AppConfig.SHEET["MEMBERS"], self._ensure_columns(df, AppConfig.HEADERS["MEMBERS"]))
        self.gs.clear_cache()

    def load_ledger(self) -> pd.DataFrame:
        df = self.gs.load_df(AppConfig.SHEET["LEDGER"])
        if df.empty:
            return pd.DataFrame(columns=AppConfig.HEADERS["LEDGER"])
        return self._ensure_columns(df, AppConfig.HEADERS["LEDGER"])

    def write_ledger(self, df: pd.DataFrame) -> None:
        self.gs.write_df(AppConfig.SHEET["LEDGER"], self._ensure_columns(df, AppConfig.HEADERS["LEDGER"]))
        self.gs.clear_cache()

    def append_ledger(self, *args, **kwargs) -> None:
        if kwargs:
            ts = kwargs.get("ts") or kwargs.get("dt_jst") or ""
            project = kwargs.get("project", "")
            person = kwargs.get("person") or kwargs.get("person_name") or ""
            type_name = kwargs.get("type_name") or kwargs.get("typ") or ""
            amount = kwargs.get("amount", 0)
            memo = kwargs.get("memo") or kwargs.get("note") or ""
            evidence = kwargs.get("evidence") or kwargs.get("evidence_url") or ""
            line_uid = kwargs.get("line_uid") or kwargs.get("line_user_id") or ""
            line_name = kwargs.get("line_name") or kwargs.get("line_display_name") or ""
            source = kwargs.get("source", "APP")
        else:
            ts, project, person, type_name, amount, memo, evidence, line_uid, line_name, *rest = args
            source = rest[0] if rest else "APP"
        row = [ts, project, person, type_name, amount, memo, evidence, line_uid, line_name, source]
        self.gs.append_row(AppConfig.SHEET["LEDGER"], row)
        self.gs.clear_cache()

    def load_line_users(self) -> pd.DataFrame:
        df = self.gs.load_df(AppConfig.SHEET["LINEUSERS"])
        if df.empty:
            return pd.DataFrame(columns=AppConfig.HEADERS["LINEUSERS"])
        return self._ensure_columns(df, AppConfig.HEADERS["LINEUSERS"])

    def load_apr_summary(self) -> pd.DataFrame:
        df = self.gs.load_df(AppConfig.SHEET["APR_SUMMARY"])
        if df.empty:
            return pd.DataFrame(columns=AppConfig.HEADERS["APR_SUMMARY"])
        return self._ensure_columns(df, AppConfig.HEADERS["APR_SUMMARY"])

    def write_apr_summary(self, df: pd.DataFrame) -> None:
        self.gs.write_df(AppConfig.SHEET["APR_SUMMARY"], self._ensure_columns(df, AppConfig.HEADERS["APR_SUMMARY"]))
        self.gs.clear_cache()

    def load_smartvault_history(self) -> pd.DataFrame:
        df = self.gs.load_df(AppConfig.SHEET["SMARTVAULT_HISTORY"])
        if df.empty:
            return pd.DataFrame(columns=AppConfig.HEADERS["SMARTVAULT_HISTORY"])
        return self._ensure_columns(df, AppConfig.HEADERS["SMARTVAULT_HISTORY"])

    def load_ocr_transaction_history(self) -> pd.DataFrame:
        df = self.gs.load_df(AppConfig.SHEET["OCR_TRANSACTION_HISTORY"])
        if df.empty:
            return pd.DataFrame(columns=AppConfig.HEADERS["OCR_TRANSACTION_HISTORY"])
        return self._ensure_columns(df, AppConfig.HEADERS["OCR_TRANSACTION_HISTORY"])

    def load_apr_auto_queue(self) -> pd.DataFrame:
        df = self.gs.load_df(AppConfig.SHEET["APR_AUTO_QUEUE"])
        if df.empty:
            return pd.DataFrame(columns=AppConfig.HEADERS["APR_AUTO_QUEUE"])
        return self._ensure_columns(df, AppConfig.HEADERS["APR_AUTO_QUEUE"])

    def active_projects(self, settings_df: pd.DataFrame) -> list[str]:
        if settings_df is None or settings_df.empty:
            return []
        df = settings_df.copy()
        if "Active" in df.columns:
            active_mask = df["Active"].astype(str).str.lower().isin(["true", "1", "yes", "on"])
            df = df[active_mask]
        if "Project_Name" not in df.columns:
            return []
        return (
            df["Project_Name"].astype(str).str.strip().replace("", pd.NA).dropna().tolist()
        )

    def existing_apr_keys_for_date(self, date_ymd: str) -> set[tuple[str, str]]:
        ledger_df = self.load_ledger()
        if ledger_df.empty:
            return set()
        df = ledger_df.copy()
        if "Datetime_JST" not in df.columns or "Type" not in df.columns:
            return set()
        df = df[df["Type"].astype(str).str.strip() == "APR"].copy()
        if df.empty:
            return set()
        df["DateOnly"] = df["Datetime_JST"].astype(str).str.slice(0, 10)
        df = df[df["DateOnly"] == str(date_ymd).strip()].copy()
        if "Project_Name" not in df.columns or "PersonName" not in df.columns:
            return set()
        return set(zip(df["Project_Name"].astype(str).str.strip(), df["PersonName"].astype(str).str.strip()))

    def reset_today_apr_records(self, date_ymd: str, project: str) -> tuple[int, int]:
        ledger_df = self.load_ledger()
        if ledger_df.empty:
            return 0, 0
        df = ledger_df.copy()
        df["DateOnly"] = df["Datetime_JST"].astype(str).str.slice(0, 10)
        project_mask = df["Project_Name"].astype(str).str.strip() == str(project).strip()
        day_mask = df["DateOnly"] == str(date_ymd).strip()
        apr_mask = df["Type"].astype(str).str.strip() == "APR"
        line_mask = df["Type"].astype(str).str.strip() == "LINE"
        delete_mask = project_mask & day_mask & (apr_mask | line_mask)
        deleted_apr = int((project_mask & day_mask & apr_mask).sum())
        deleted_line = int((project_mask & day_mask & line_mask).sum())
        kept = df.loc[~delete_mask, AppConfig.HEADERS["LEDGER"]].copy()
        self.write_ledger(kept)
        return deleted_apr, deleted_line
