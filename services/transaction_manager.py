from __future__ import annotations

from typing import Any, List, Dict, Set

from repository.repository import Repository
from core.utils import U


class TransactionManager:
    """
    OCR取引履歴の保存と重複判定を担当
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

    # =========================================================
    # Sheet
    # =========================================================
    def ensure_sheet(self) -> None:
        book = self.repo.gs.book

        try:
            ws = book.worksheet(self.SHEET_NAME)
        except Exception:
            ws = book.add_worksheet(title=self.SHEET_NAME, rows=5000, cols=20)
            ws.append_row(self.HEADERS, value_input_option="USER_ENTERED")
            return

        try:
            first = ws.row_values(1)
        except Exception:
            return

        if not first:
            ws.append_row(self.HEADERS, value_input_option="USER_ENTERED")
            return

        current = [str(c).strip() for c in first]
        if current != self.HEADERS:
            merged = current[:]
            for h in self.HEADERS:
                if h not in merged:
                    merged.append(h)
            ws.update("1:1", [merged])

    # =========================================================
    # Load
    # =========================================================
    def get_existing_keys(self) -> Set[str]:
        self.ensure_sheet()

        try:
            ws = self.repo.gs.book.worksheet(self.SHEET_NAME)
            values = ws.get_all_values()
        except Exception:
            return set()

        if not values or len(values) < 2:
            return set()

        headers = values[0]
        if "Unique_Key" not in headers:
            return set()

        key_idx = headers.index("Unique_Key")
        out: Set[str] = set()

        for row in values[1:]:
            padded = row + [""] * (len(headers) - len(row))
            key = str(padded[key_idx]).strip()
            if key:
                out.add(key)

        return out

    # =========================================================
    # Save
    # =========================================================
    def append_rows(self, rows: List[List[Any]]) -> None:
        if not rows:
            return

        self.ensure_sheet()
        ws = self.repo.gs.book.worksheet(self.SHEET_NAME)

        for row in rows:
            ws.append_row(row, value_input_option="USER_ENTERED")

    def build_sheet_row(
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
        created_at_jst: str | None = None,
    ) -> List[Any]:
        created_at = created_at_jst or U.fmt_dt(U.now_jst())

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

    # =========================================================
    # Transaction process
    # =========================================================
    def split_new_and_duplicate_rows(
        self,
        tx_rows: List[Dict[str, Any]],
        source_image: str,
        source_project: str,
    ) -> Dict[str, Any]:
        existing_keys = self.get_existing_keys()
        created_at = U.fmt_dt(U.now_jst())

        new_sheet_rows: List[List[Any]] = []
        view_rows: List[Dict[str, Any]] = []

        total_detected = 0.0
        total_new = 0.0
        duplicate_count = 0

        for row in tx_rows:
            unique_key = str(row["unique_key"]).strip()
            amount_usd = float(row["amount_usd"])
            platform = str(row.get("platform", "")).strip()
            is_duplicate = unique_key in existing_keys

            total_detected += amount_usd

            if is_duplicate:
                duplicate_count += 1
            else:
                existing_keys.add(unique_key)
                total_new += amount_usd

                new_sheet_rows.append(
                    self.build_sheet_row(
                        unique_key=unique_key,
                        date_label=str(row.get("date_label", "")).strip(),
                        time_label=str(row.get("time_label", "")).strip(),
                        type_label=str(row.get("type_label", "")).strip(),
                        amount_usd=amount_usd,
                        source_image=source_image,
                        source_project=source_project,
                        platform=platform,
                        raw_text=str(row.get("raw_text", "")),
                        token_amount=row.get("token_amount", ""),
                        token_symbol=str(row.get("token_symbol", "")),
                        created_at_jst=created_at,
                    )
                )

            view_rows.append(
                {
                    "Platform": platform,
                    "Row": row.get("row_index", ""),
                    "Date_Label": str(row.get("date_label", "")).strip(),
                    "Time_Label": str(row.get("time_label", "")).strip(),
                    "Type_Label": str(row.get("type_label", "")).strip(),
                    "Amount_USD": f"{amount_usd:.2f}",
                    "Unique_Key": unique_key,
                    "Status": "重複" if is_duplicate else "新規",
                }
            )

        return {
            "new_sheet_rows": new_sheet_rows,
            "view_rows": view_rows,
            "total_detected": total_detected,
            "total_new": total_new,
            "duplicate_count": duplicate_count,
        }

    def save_new_transactions(
        self,
        tx_rows: List[Dict[str, Any]],
        source_image: str,
        source_project: str,
    ) -> Dict[str, Any]:
        result = self.split_new_and_duplicate_rows(
            tx_rows=tx_rows,
            source_image=source_image,
            source_project=source_project,
        )

        if result["new_sheet_rows"]:
            self.append_rows(result["new_sheet_rows"])

        return result
