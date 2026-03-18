from __future__ import annotations

import pandas as pd
import streamlit as st

from config import AppConfig
from core.auth import AdminAuth
from core.utils import U
from repository.repository import Repository
from services.gsheet_service import GSheetService
from store.datastore import DataStore


class HelpPage:

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

    def __init__(self, repo: Repository, store: DataStore):
        self.repo = repo
        self.store = store


    def render(self, gs: GSheetService, settings_df: pd.DataFrame):

        st.subheader("❓ 操作マニュアル / ヘルプ")
        st.caption(f"{AppConfig.RANK_LABEL} / 管理者: {AdminAuth.current_label()}")

        st.markdown(
        """
このページでは **システムの設定方法 / APIキー / シート構造 / OCR / トラブル対処** をまとめています。

このアプリは

**コードを変更せずに設定だけで運用を変えられる**

設計になっています。
"""
        )

        st.divider()

        # =========================================================
        # 接続情報
        # =========================================================

        with st.expander("① 接続情報", expanded=False):

            st.code(f"""
Spreadsheet ID
{gs.spreadsheet_id}

URL
{gs.spreadsheet_url()}
""")

            st.code(f"""
Settings                = {gs.names.SETTINGS}
Members                 = {gs.names.MEMBERS}
Ledger                  = {gs.names.LEDGER}
LineUsers               = {gs.names.LINEUSERS}
APR_Summary             = {gs.names.APR_SUMMARY}
SmartVault_History      = {gs.names.SMARTVAULT_HISTORY}
OCR_Transaction_History = {self.OCR_TX_HISTORY_SHEET}
""")


        # =========================================================
        # Secrets
        # =========================================================

        with st.expander("② Secrets設定", expanded=False):

            st.markdown("### Secrets例")

            st.code("""
[connections.gsheets]
spreadsheet = "YOUR_SPREADSHEET_ID"

[connections.gsheets.credentials]
type = "service_account"
project_id = "PROJECT_ID"
private_key_id = "PRIVATE_KEY_ID"
private_key = \"\"\"-----BEGIN PRIVATE KEY-----
PRIVATE_KEY
-----END PRIVATE KEY-----\"\"\"
client_email = "CLIENT_EMAIL"
client_id = "CLIENT_ID"
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "CERT_URL"

[admin]
pin = "0000"

[[admin.users]]
name = "Admin A"
pin = "1111"
namespace = "A"

[[admin.users]]
name = "Admin B"
pin = "2222"
namespace = "B"

[line.tokens]
A = "LINE_TOKEN_A"
B = "LINE_TOKEN_B"

[imgbb]
api_key = "IMGBB_API_KEY"

[ocrspace]
api_key = "OCR_API_KEY"

[local_paths]
apr_watch_folder = "/Users/yourname/Desktop/smartvault_images"
""")


        # =========================================================
        # シート構造
        # =========================================================

        with st.expander("③ シート構造", expanded=False):

            st.markdown("### Settings")

            st.code("\t".join(AppConfig.HEADERS["SETTINGS"]))

            st.markdown("### Members")

            st.code("\t".join(AppConfig.HEADERS["MEMBERS"]))

            st.markdown("### Ledger")

            st.code("\t".join(AppConfig.HEADERS["LEDGER"]))

            st.markdown("### LineUsers")

            st.code("\t".join(AppConfig.HEADERS["LINEUSERS"]))


        # =========================================================
        # OCR取引履歴
        # =========================================================

        with st.expander("④ OCR取引履歴シート", expanded=False):

            st.markdown("### シート名")

            st.code(self.OCR_TX_HISTORY_SHEET)

            st.markdown("### 項目名（コピー用）")

            st.code("\t".join(self.OCR_TX_HISTORY_HEADERS))

            st.markdown("""
このシートには

OCRで取得した **受取トランザクション** が保存されます。

重複防止のため
