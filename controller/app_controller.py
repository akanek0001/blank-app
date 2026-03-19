from __future__ import annotations

import streamlit as st

from config import AppConfig
from engine.finance_engine import FinanceEngine
from repository.repository import Repository
from services.gsheet_service import GSheetService
from store.datastore import DataStore

# 既存ページ
from app_pages.apr_page import APRPage
from ui.admin import AdminPage
from ui.help import HelpPage

# 任意ページ（未実装でも落とさない）
try:
    from app_pages.dashboard_page import DashboardPage
except Exception:
    DashboardPage = None

try:
    from app_pages.cash_page import CashPage
except Exception:
    CashPage = None

try:
    from core.auth import AdminAuth
except Exception:
    AdminAuth = None


class _FallbackPage:
    def __init__(self, title: str, message: str):
        self.title = title
        self.message = message

    def render(self, *args, **kwargs):
        st.subheader(self.title)
        st.info(self.message)


class AppController:
    """
    役割:
    - 共通サービス初期化
    - サイドバー制御
    - 各ページへのデータ受け渡し

    方針:
    - ページごとのロジックは各 Page クラス側に持たせる
    - controller は配線だけに集中
    - 未実装ページがあってもアプリ全体は落とさない
    """

    def __init__(self):
        self.gs: GSheetService | None = None
        self.repo: Repository | None = None
        self.engine: FinanceEngine | None = None
        self.store: DataStore | None = None

        self.dashboard_page = None
        self.apr_page: APRPage | None = None
        self.cash_page = None
        self.admin_page: AdminPage | None = None
        self.help_page: HelpPage | None = None

    # =========================================================
    # Service setup
    # =========================================================
    def _get_namespace(self) -> str:
        try:
            if AdminAuth is not None and hasattr(AdminAuth, "current_namespace"):
                ns = AdminAuth.current_namespace()
                if str(ns).strip():
                    return str(ns).strip()
        except Exception:
            pass
        return "A"

    def _get_spreadsheet_id(self) -> str:
        spreadsheet_id = str(getattr(AppConfig, "SPREADSHEET_ID", "")).strip()
        if spreadsheet_id:
            return spreadsheet_id

        st.error("AppConfig.SPREADSHEET_ID が未設定です。")
        st.stop()

    def setup_services(self) -> None:
        spreadsheet_id = self._get_spreadsheet_id()
        namespace = self._get_namespace()

        self.gs = GSheetService(
            spreadsheet_id=spreadsheet_id,
            namespace=namespace,
        )
        self.repo = Repository(self.gs)
        self.engine = FinanceEngine()
        self.store = DataStore(self.repo, self.engine)

        # -----------------------------
        # Pages
        # -----------------------------
        if DashboardPage is not None:
            try:
                self.dashboard_page = DashboardPage(self.repo, self.engine, self.store)
            except TypeError:
                try:
                    self.dashboard_page = DashboardPage(self.repo, self.store)
                except TypeError:
                    try:
                        self.dashboard_page = DashboardPage(self.repo)
                    except Exception:
                        self.dashboard_page = _FallbackPage(
                            "📊 ダッシュボード",
                            "DashboardPage の初期化に失敗しました。",
                        )
                except Exception:
                    self.dashboard_page = _FallbackPage(
                        "📊 ダッシュボード",
                        "DashboardPage の初期化に失敗しました。",
                    )
            except Exception:
                self.dashboard_page = _FallbackPage(
                    "📊 ダッシュボード",
                    "DashboardPage の初期化に失敗しました。",
                )
        else:
            self.dashboard_page = _FallbackPage(
                "📊 ダッシュボード",
                "dashboard_page.py はまだ接続していません。",
            )

        self.apr_page = APRPage(self.repo, self.engine, self.store)

        if CashPage is not None:
            try:
                self.cash_page = CashPage(self.repo, self.engine, self.store)
            except TypeError:
                try:
                    self.cash_page = CashPage(self.repo, self.store)
                except TypeError:
                    try:
                        self.cash_page = CashPage(self.repo)
                    except Exception:
                        self.cash_page = _FallbackPage(
                            "💸 入金/出金",
                            "CashPage の初期化に失敗しました。",
                        )
                except Exception:
                    self.cash_page = _FallbackPage(
                        "💸 入金/出金",
                        "CashPage の初期化に失敗しました。",
                    )
            except Exception:
                self.cash_page = _FallbackPage(
                    "💸 入金/出金",
                    "CashPage の初期化に失敗しました。",
                )
        else:
            self.cash_page = _FallbackPage(
                "💸 入金/出金",
                "cash_page.py はまだ接続していません。",
            )

        self.admin_page = AdminPage(self.repo, self.store)
        self.help_page = HelpPage(self.repo, self.store)

    # =========================================================
    # Sidebar
    # =========================================================
    def _render_sidebar(self) -> str:
        st.sidebar.title(AppConfig.APP_TITLE)

        try:
            admin_label = AdminAuth.current_label() if AdminAuth is not None else "Admin"
        except Exception:
            admin_label = "Admin"

        try:
            namespace = self._get_namespace()
        except Exception:
            namespace = "A"

        st.sidebar.caption(f"管理者: {admin_label} / Namespace: {namespace}")

        menu_items = [
            AppConfig.PAGE.get("DASHBOARD", "📊 ダッシュボード"),
            AppConfig.PAGE.get("APR", "📈 APR"),
            AppConfig.PAGE.get("CASH", "💸 入金/出金"),
            AppConfig.PAGE.get("ADMIN", "⚙️ 管理"),
            AppConfig.PAGE.get("HELP", "❓ ヘルプ"),
        ]

        page = st.sidebar.radio(
            "メニュー",
            menu_items,
            index=0,
        )
        return page

    # =========================================================
    # Main
    # =========================================================
    def run(self) -> None:
        self.setup_services()
        data = self.store.load()

        page = self._render_sidebar()

        page_dashboard = AppConfig.PAGE.get("DASHBOARD", "📊 ダッシュボード")
        page_apr = AppConfig.PAGE.get("APR", "📈 APR")
        page_cash = AppConfig.PAGE.get("CASH", "💸 入金/出金")
        page_admin = AppConfig.PAGE.get("ADMIN", "⚙️ 管理")
        page_help = AppConfig.PAGE.get("HELP", "❓ ヘルプ")

        if page == page_dashboard:
            self.dashboard_page.render(
                data["settings_df"],
                data["members_df"],
                data["ledger_df"],
                data["apr_summary_df"],
            )

        elif page == page_apr:
            self.apr_page.render(
                data["settings_df"],
                data["members_df"],
            )

        elif page == page_cash:
            self.cash_page.render(
                data["settings_df"],
                data["members_df"],
                data["ledger_df"],
            )

        elif page == page_admin:
            self.admin_page.render(
                data["settings_df"],
                data["members_df"],
                data["line_users_df"],
            )

        elif page == page_help:
            self.help_page.render(
                self.gs,
                data["settings_df"],
            )

        else:
            st.warning("不明なメニューです。")
