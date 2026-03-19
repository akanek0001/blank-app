from __future__ import annotations

from datetime import timezone, timedelta


class AppConfig:
    # =========================================================
    # 基本設定
    # =========================================================
    APP_TITLE = "APR資産運用管理システム"
    APP_ICON = "🏦"
    PAGE_LAYOUT = "wide"
    JST = timezone(timedelta(hours=9), "JST")

    # 必要ならここを書き換え
    SPREADSHEET_ID = "1z6XuFavFlUMYcsXmASlTgqvDcvNKuhCoSZePb-PHyn0"

    # =========================================================
    # 表示ラベル
    # =========================================================
    STATUS = {
        "ON": "🟢運用中",
        "OFF": "🔴停止",
    }

    RANK = {
        "MASTER": "Master",
        "ELITE": "Elite",
    }

    FACTOR = {
        "MASTER": 0.67,
        "ELITE": 0.60,
    }

    RANK_LABEL = "👑Master=67% / 🥈Elite=60%"

    PAGE = {
        "DASHBOARD": "📊 ダッシュボード",
        "APR": "📈 APR",
        "CASH": "💸 入金/出金",
        "ADMIN": "⚙️ 管理",
        "HELP": "❓ ヘルプ",
    }

    PROJECT = {
        "PERSONAL": "PERSONAL",
    }

    COMPOUND = {
        "DAILY": "daily",
        "MONTHLY": "monthly",
        "NONE": "none",
    }

    TYPE = {
        "APR": "APR",
        "LINE": "LINE",
        "DEPOSIT": "DEPOSIT",
        "WITHDRAW": "WITHDRAW",
    }

    SOURCE = {
        "APP": "APP",
        "MAKE": "MAKE",
    }

    APR_LINE_NOTE_KEYWORD = "APR配当"

    # =========================================================
    # シート名
    # =========================================================
    SHEET = {
        "SETTINGS": "Settings",
        "MEMBERS": "Members",
        "LEDGER": "Ledger",
        "LINEUSERS": "LineUsers",
        "APR_SUMMARY": "APR_Summary",
        "SMARTVAULT_HISTORY": "SmartVault_History",
    }

    # =========================================================
    # セッションキー
    # =========================================================
    SESSION_KEYS = {
        "SETTINGS": "settings_df",
        "MEMBERS": "members_df",
        "LEDGER": "ledger_df",
        "LINEUSERS": "line_users_df",
        "APR_SUMMARY": "apr_summary_df",
    }

    # =========================================================
    # Settingsヘッダ
    # =========================================================
    HEADERS = {
        "SETTINGS": [
            "Project_Name",
            "Net_Factor",
            "IsCompound",
            "Compound_Timing",
            "Active",
            "UpdatedAt_JST",

            # 汎用OCR範囲 PC
            "Crop_Left_Ratio_PC",
            "Crop_Top_Ratio_PC",
            "Crop_Right_Ratio_PC",
            "Crop_Bottom_Ratio_PC",

            # 汎用OCR範囲 Mobile
            "Crop_Left_Ratio_Mobile",
            "Crop_Top_Ratio_Mobile",
            "Crop_Right_Ratio_Mobile",
            "Crop_Bottom_Ratio_Mobile",

            # 3領域OCR Mobile
            "TX_Scan_BaseTop_Ratio_Mobile",
            "TX_Scan_Step_Ratio_Mobile",
            "TX_Scan_MaxRows_Mobile",

            "TX_Date_Left_Ratio_Mobile",
            "TX_Date_Right_Ratio_Mobile",
            "TX_Date_Top_Offset_Ratio_Mobile",
            "TX_Date_Bottom_Offset_Ratio_Mobile",

            "TX_Type_Left_Ratio_Mobile",
            "TX_Type_Right_Ratio_Mobile",
            "TX_Type_Top_Offset_Ratio_Mobile",
            "TX_Type_Bottom_Offset_Ratio_Mobile",

            "TX_USD_Left_Ratio_Mobile",
            "TX_USD_Right_Ratio_Mobile",
            "TX_USD_Top_Offset_Ratio_Mobile",
            "TX_USD_Bottom_Offset_Ratio_Mobile",

            # SmartVault PC座標
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
        ],

        "MEMBERS": [
            "Project_Name",
            "PersonName",
            "Principal",
            "Line_User_ID",
            "LINE_DisplayName",
            "Rank",
            "IsActive",
            "CreatedAt_JST",
            "UpdatedAt_JST",
        ],

        "LEDGER": [
            "Datetime_JST",
            "Project_Name",
            "PersonName",
            "Type",
            "Amount",
            "Note",
            "Evidence_URL",
            "Line_User_ID",
            "LINE_DisplayName",
            "Source",
        ],

        "LINEUSERS": [
            "Line_User_ID",
            "Line_User",
        ],

        "APR_SUMMARY": [
            "Date_JST",
            "PersonName",
            "Total_APR",
            "APR_Count",
            "Asset_Ratio",
            "LINE_DisplayName",
        ],

        "SMARTVAULT_HISTORY": [
            "Datetime_JST",
            "Project_Name",
            "Liquidity",
            "Yesterday_Profit",
            "APR",
            "Source_Mode",
            "OCR_Liquidity",
            "OCR_Yesterday_Profit",
            "OCR_APR",
            "Evidence_URL",
            "Admin_Name",
            "Admin_Namespace",
            "Note",
        ],
    }

    # =========================================================
    # OCRデフォルト
    # =========================================================
    OCR_DEFAULTS_PC = {
        "Crop_Left_Ratio_PC": 0.000,
        "Crop_Top_Ratio_PC": 0.000,
        "Crop_Right_Ratio_PC": 1.000,
        "Crop_Bottom_Ratio_PC": 1.000,
    }

    OCR_DEFAULTS_MOBILE = {
        "Crop_Left_Ratio_Mobile": 0.000,
        "Crop_Top_Ratio_Mobile": 0.000,
        "Crop_Right_Ratio_Mobile": 1.000,
        "Crop_Bottom_Ratio_Mobile": 1.000,
    }

    SMARTVAULT_BOXES_MOBILE = {
        "TOTAL_LIQUIDITY": {
            "left": 0.05,
            "top": 0.25,
            "right": 0.40,
            "bottom": 0.34,
        },
        "YESTERDAY_PROFIT": {
            "left": 0.41,
            "top": 0.25,
            "right": 0.69,
            "bottom": 0.34,
        },
        "APR": {
            "left": 0.70,
            "top": 0.25,
            "right": 0.93,
            "bottom": 0.34,
        },
    }
