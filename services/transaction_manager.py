from __future__ import annotations
from typing import Any, Dict, List, Set

from repository.repository import Repository
from core.utils import U


class TransactionManager:
    """
    OCR取引履歴の管理クラス
    """

    SHEET_NAME = "OCR_Transaction_History"

    HEADERS = [
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

    def __init__(self, repo: Repository):
        self.repo = repo

    def ensure_sheet(self) -> None:
        book = self.repo.gs.book

        try:
            ws = book.worksheet(self.SHEET_NAME)
        except Exception:
            ws = book.add_worksheet(title=self.SHEET_NAME, rows=5000, cols=20)
            ws.append_row(self.HEADERS, value_input_option="USER_ENTERED")
            return

        try:
            values = ws.get_all_values()
        except Exception:
            return

        if not values:
            ws.append_row(self.HEADERS, value_input_option="USER_ENTERED")
            return

        current = [str(c).strip() for c in values[0]]
        if current != self.HEADERS:
            merged = current[:]
            for h in self.HEADERS:
                if h not in merged:
                    merged.append(h)
            ws.update("1:1", [merged])

    def get_existing_keys(self) -> Set[str]:
        self.ensure_sheet()

        try:
            ws = self.repo.gs.book.worksheet(self.SHEET_NAME)
            values = ws.get_all_values()
        except Exception:
            return set()

        if len(values) <= 1:
            return set()

        headers = values[0]
        if "Unique_Key" not in headers:
            return set()

        idx = headers.index("Unique_Key")
        keys: Set[str] = set()

        for row in values[1:]:
            if len(row) > idx:
                key = str(row[idx]).strip()
                if key:
                    keys.add(key)

        return keys

    def build_row(
        self,
        unique_key: str,
        date_label: str,
        time_label: str,
        type_label: str,
        amount_usd: float,
        source_image: str,
        source_project: str,
        platform: str,
        raw_text: str,
        token_amount: Any = "",
        token_symbol: str = "",
    ) -> List[Any]:
        created_at = U.fmt_dt(U.now_jst())

        return [
            unique_key,
            date_label,
            time_label,
            type_label,
            float(amount_usd),
            token_amount,
            token_symbol,
            source_image,
            source_project,
            platform,
            raw_text,
            created_at,
        ]

    def save_new_transactions(
        self,
        tx_rows: List[Dict[str, Any]],
        source_image: str,
        source_project: str,
    ) -> Dict[str, Any]:
        existing_keys = self.get_existing_keys()
        ws = self.repo.gs.book.worksheet(self.SHEET_NAME)

        new_rows: List[List[Any]] = []
        view_rows: List[Dict[str, Any]] = []

        total_detected = 0.0
        total_new = 0.0
        duplicate_count = 0

        for row in tx_rows:
            unique_key = str(row["unique_key"]).strip()
            amount = float(row["amount_usd"])

            total_detected += amount

            if unique_key in existing_keys:
                duplicate_count += 1
                view_rows.append({
                    "Platform": str(row.get("platform", "")),
                    "Status": "重複",
                    "Unique_Key": unique_key,
                    "Amount_USD": f"{amount:.2f}",
                })
                continue

            existing_keys.add(unique_key)
            total_new += amount

            sheet_row = self.build_row(
                unique_key=unique_key,
                date_label=str(row.get("date_label", "")),
                time_label=str(row.get("time_label", "")),
                type_label=str(row.get("type_label", "")),
                amount_usd=amount,
                source_image=source_image,
                source_project=source_project,
                platform=str(row.get("platform", "")),
                raw_text=str(row.get("raw_text", "")),
                token_amount=row.get("token_amount", ""),
                token_symbol=str(row.get("token_symbol", "")),
            )

            new_rows.append(sheet_row)

            view_rows.append({
                "Platform": str(row.get("platform", "")),
                "Status": "新規",
                "Unique_Key": unique_key,
                "Amount_USD": f"{amount:.2f}",
            })

        for r in new_rows:
            ws.append_row(r, value_input_option="USER_ENTERED")

        return {
            "view_rows": view_rows,
            "new_rows": new_rows,
            "duplicate_count": duplicate_count,
            "total_detected": total_detected,
            "total_new": total_new,
        }
