from __future__ import annotations

import streamlit as st

from config import AppConfig
from engine.finance_engine import FinanceEngine
from app_pages.apr_page import APRPage
from repository.repository import Repository
from services.gsheet_service import GSheetService
from store.datastore import DataStore
from ui.admin import AdminPage
from ui.help import HelpPage


class AppController:
    def __init__(self):
        self.gs: GSheetService | None = None
        self.repo: Repository | None = None
        self.engine: FinanceEngine | None = None
        self.store: DataStore | None = None
        self.apr_page: APRPage | None = None
        self.admin_page: AdminPage | None = None
        self.help_page: HelpPage | None = None

    def setup_services(self) -> None:
        spreadsheet_id = AppConfig.SPREADSHEET_ID
        namespace = "A"

        self.gs = GSheetService(
            spreadsheet_id=spreadsheet_id,
            namespace=namespace,
        )
        self.repo = Repository(self.gs)
        self.engine = FinanceEngine()
        self.store = DataStore(self.repo)

        self.apr_page = APRPage(self.repo, self.engine, self.store)
        self.admin_page = AdminPage(self.repo, self.store)
        self.help_page = HelpPage()

    def run(self) -> None:
        self.setup_services()
        data = self.store.load_all()

        page = st.sidebar.radio(
            "メニュー",
            ["APR", "管理", "ヘルプ"],
            index=0,
        )

        if page == "APR":
            self.apr_page.render(
                data["settings_df"],
                data["members_df"],
            )
        elif page == "管理":
            self.admin_page.render(
                data["settings_df"],
                data["members_df"],
                data["line_users_df"],
            )
        else:
            self.help_page.render()
