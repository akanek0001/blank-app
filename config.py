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

    # =========================================================
    # ステータス
    # =========================================================

    STATUS = {
        "ON": "🟢運用中",
        "OFF": "🔴停止",
    }

    # =========================================================
    # ランク
    # =========================================================

    RANK = {
        "MASTER": "Master",
        "ELITE": "Elite",
    }

    FACTOR = {
        "MASTER": 0.67,
        "ELITE": 0.60,
    }

    RANK_LABEL = "👑Master=67% / 🥈Elite=60%"

    # =========================================================
    # プロジェクト
    # =========================================================

    PROJECT = {
        "PERSONAL": "PERSONAL"
    }

    # =========================================================
    # 複利
    # =========================================================

    COMPOUND = {
        "DAILY": "daily",
        "MONTHLY": "monthly",
        "NONE": "none",
    }

    # =========================================================
    # Ledger Type
    # =========================================================

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
    # スプレッドシートヘッダ
    # =========================================================

    HEADERS = {

        "SETTINGS": [

            "Project_Name",
            "Net_Factor",
            "IsCompound",
            "Compound_Timing",
            "Active",
            "UpdatedAt_JST",

            # OCR PC
            "OCR_Left_Ratio_PC",
            "OCR_Top_Ratio_PC",
            "OCR_Right_Ratio_PC",
            "OCR_Bottom_Ratio_PC",

            # OCR Mobile
            "OCR_Left_Ratio_Mobile",
            "OCR_Top_Ratio_Mobile",
            "OCR_Right_Ratio_Mobile",
            "OCR_Bottom_Ratio_Mobile",

            # =========================================================
            # 3領域OCR Mobile
            # =========================================================

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
    }

    # =========================================================
    # OCR デフォルト値 PC
    # =========================================================

    OCR_DEFAULTS_PC = {

        "OCR_Left_Ratio_PC": 0.000,
        "OCR_Top_Ratio_PC": 0.000,
        "OCR_Right_Ratio_PC": 1.000,
        "OCR_Bottom_Ratio_PC": 1.000,

    }

    # =========================================================
    # OCR デフォルト値 Mobile
    # =========================================================

    OCR_DEFAULTS_MOBILE = {

        "OCR_Left_Ratio_Mobile": 0.000,
        "OCR_Top_Ratio_Mobile": 0.000,
        "OCR_Right_Ratio_Mobile": 1.000,
        "OCR_Bottom_Ratio_Mobile": 1.000,

    }
