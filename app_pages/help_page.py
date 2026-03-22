from __future__ import annotations

import io
import re
from typing import Dict, List

import pandas as pd
import streamlit as st
from PIL import Image, ImageDraw

from config import AppConfig
from core.auth import AdminAuth
from core.utils import U
from repository.repository import Repository
from services.external_service import ExternalService


class HelpPage:
    def __init__(self, repo: Repository):
        self.repo = repo

    # =========================
    # helper
    # =========================
    def _safe_df(self, df: pd.DataFrame) -> pd.DataFrame:
        if df is None or df.empty:
            return pd.DataFrame()
        out = df.copy()
        out = out.loc[:, ~out.columns.duplicated()]
        out.columns = [str(c).strip() for c in out.columns]
        return out.reset_index(drop=True)

    def _safe_float(self, value, default: float) -> float:
        try:
            s = str(value).strip()
            if s == "":
                return float(default)
            return float(s)
        except Exception:
            return float(default)

    def _safe_str(self, value, default: str = "") -> str:
        try:
            s = str(value)
            return s.strip() if s is not None else default
        except Exception:
            return default

    def _num(self, text: str) -> float:
        m = re.findall(r"[-+]?\d*\.\d+|\d+", str(text).replace(",", ""))
        return float(m[0]) if m else 0.0

    def _crop(self, img: Image.Image, box: Dict[str, float]) -> Image.Image:
        w, h = img.size
        return img.crop(
            (
                int(box["left"] * w),
                int(box["top"] * h),
                int(box["right"] * w),
                int(box["bottom"] * h),
            )
        )

    def _draw_boxes(self, img: Image.Image, boxes: Dict[str, Dict[str, float]]) -> Image.Image:
        d = ImageDraw.Draw(img)
        w, h = img.size

        for _, b in boxes.items():
            d.rectangle(
                [
                    (b["left"] * w, b["top"] * h),
                    (b["right"] * w, b["bottom"] * h),
                ],
                outline="red",
                width=3,
            )
        return img

    def _project_row(self, settings_df: pd.DataFrame, project: str) -> pd.Series:
        sdf = settings_df.copy()
        sdf["Project_Name"] = sdf["Project_Name"].astype(str).str.strip()
        hit = sdf[sdf["Project_Name"] == str(project).strip()]
        return hit.iloc[0]

    def _header_text(self, key: str) -> str:
        return "\n".join(AppConfig.HEADERS[key])

    def _sheet_names_for_ns(self, ns: str) -> List[str]:
        return [
            U.sheet_name("Settings", ns),
            U.sheet_name("Members", ns),
            U.sheet_name("Ledger", ns),
            U.sheet_name("LineUsers", ns),
            U.sheet_name("APR_Summary", ns),
            U.sheet_name("SmartVault_History", ns),
            U.sheet_name("OCR_Transaction", ns),
            U.sheet_name("OCR_Transaction_History", ns),
            U.sheet_name("APR_Auto_Queue", ns),
        ]

    def _smartvault_boxes_from_row(self, row: pd.Series) -> Dict[str, Dict[str, float]]:
        return {
            "LIQUIDITY": {
                "left": self._safe_float(row.get("SV_Total_Liquidity_Left_Mobile", 0.05), 0.05),
                "top": self._safe_float(row.get("SV_Total_Liquidity_Top_Mobile", 0.25), 0.25),
                "right": self._safe_float(row.get("SV_Total_Liquidity_Right_Mobile", 0.40), 0.40),
                "bottom": self._safe_float(row.get("SV_Total_Liquidity_Bottom_Mobile", 0.34), 0.34),
            },
            "YESTERDAY_PROFIT": {
                "left": self._safe_float(row.get("SV_Yesterday_Profit_Left_Mobile", 0.40), 0.40),
                "top": self._safe_float(row.get("SV_Yesterday_Profit_Top_Mobile", 0.25), 0.25),
                "right": self._safe_float(row.get("SV_Yesterday_Profit_Right_Mobile", 0.70), 0.70),
                "bottom": self._safe_float(row.get("SV_Yesterday_Profit_Bottom_Mobile", 0.34), 0.34),
            },
            "APR": {
                "left": self._safe_float(row.get("SV_APR_Left_Mobile", 0.70), 0.70),
                "top": self._safe_float(row.get("SV_APR_Top_Mobile", 0.25), 0.25),
                "right": self._safe_float(row.get("SV_APR_Right_Mobile", 0.95), 0.95),
                "bottom": self._safe_float(row.get("SV_APR_Bottom_Mobile", 0.34), 0.34),
            },
        }

    def _save_settings_row(self, settings_df: pd.DataFrame, project: str, updates: Dict[str, object]) -> None:
        sdf = settings_df.copy()
        sdf = sdf.loc[:, ~sdf.columns.duplicated()]
        sdf["Project_Name"] = sdf["Project_Name"].astype(str).str.strip()

        mask = sdf["Project_Name"] == str(project).strip()
        if not mask.any():
            st.error("対象プロジェクトが Settings に見つかりません。")
            return

        for key, value in updates.items():
            sdf.loc[mask, key] = value

        sdf.loc[mask, "UpdatedAt_JST"] = U.fmt_dt(U.now_jst())
        self.repo.write_settings(sdf)

    # =========================
    # render parts
    # =========================
    def _render_overview(self, namespace: str) -> None:
        st.markdown(
            f"""
## 全体アーキテクチャ（固定）

UI  
↓  
Controller  
↓  
Repository  
↓  
Service  
↓  
External（Sheets / LINE / OCR）

---

## データフロー（実際に動く流れ）

Help で設定確認 / OCRテスト  
↓  
APRページでAPR入力  
↓  
FinanceEngineで計算  
↓  
RepositoryでLedger保存  
↓  
Dashboardで表示  
↓  
必要に応じてLINE送信

---

## シート構造（完全固定 / 現在の namespace: {namespace}）

- {U.sheet_name("Settings", namespace)}
- {U.sheet_name("Members", namespace)}
- {U.sheet_name("Ledger", namespace)}
- {U.sheet_name("LineUsers", namespace)}
- {U.sheet_name("APR_Summary", namespace)}
- {U.sheet_name("SmartVault_History", namespace)}
- {U.sheet_name("OCR_Transaction", namespace)}
- {U.sheet_name("OCR_Transaction_History", namespace)}
- {U.sheet_name("APR_Auto_Queue", namespace)}

※ `_A` ではなく、必ず `__A` を使います  
※ 無印シートは使いません

---

## コア責務（重要）

### UI
- 表示と入力のみ
- 計算しない
- データ保存ロジックを持たない

### Controller
- 全体の接続
- ページ切替
- UI / Repository / Engine / Service の橋渡し

### Repository
- データの読み書き
- DataFrame整形
- シートI/O管理
- 計算しない

### Engine
- APR計算だけ担当
- 外部接続しない

### Service
- OCR / LINE / Sheets など外部接続だけ
- 計算しない

---

## 正しい実装ルール（固定）

1. UIは計算しない  
2. Repositoryはロジックを持たない  
3. Engineだけが計算する  
4. Serviceは外部接続だけ  
5. Controllerが全部をつなぐ  

---

## 使用シート役割

### {U.sheet_name("Settings", namespace)}
APR設定、OCR座標、Compound_Timing、Active管理

### {U.sheet_name("Members", namespace)}
メンバー管理（元本、LINE ID、Rank、状態）

### {U.sheet_name("Ledger", namespace)}
APR、入出金、LINE送信など全履歴

### {U.sheet_name("LineUsers", namespace)}
LINEユーザー情報

### {U.sheet_name("APR_Summary", namespace)}
日次APR集計

### {U.sheet_name("SmartVault_History", namespace)}
Liquidity、Yesterday Profit、APR の履歴

### {U.sheet_name("OCR_Transaction", namespace)}
OCR解析の作業データ

### {U.sheet_name("OCR_Transaction_History", namespace)}
OCR履歴、重複防止

### {U.sheet_name("APR_Auto_Queue", namespace)}
APR自動処理キュー

---

## 計算ロジック

### Rank係数
- Master = 0.67
- Elite = 0.60

### Compound_Timing
- daily = 日次複利
- monthly = 月次複利
- none = 複利なし

### PERSONAL
DailyAPR = Principal × APR ÷ 100 × Rank係数 ÷ 365

### GROUP
TotalAPR = 総元本 × APR ÷ 100 × Net_Factor ÷ 365  
DailyAPR = TotalAPR ÷ 対象人数

### 挙動
- daily: 元本へ即時反映
- monthly: 月次反映
- none: Ledger記録のみ
"""
        )

    def _render_sheet_columns(self, namespace: str) -> None:
        st.subheader("シート名と列名一覧（コピペ用）")

        names = {
            "SETTINGS": U.sheet_name("Settings", namespace),
            "MEMBERS": U.sheet_name("Members", namespace),
            "LEDGER": U.sheet_name("Ledger", namespace),
            "LINEUSERS": U.sheet_name("LineUsers", namespace),
            "APR_SUMMARY": U.sheet_name("APR_Summary", namespace),
            "SMARTVAULT_HISTORY": U.sheet_name("SmartVault_History", namespace),
            "OCR_TRANSACTION": U.sheet_name("OCR_Transaction", namespace),
            "OCR_TRANSACTION_HISTORY": U.sheet_name("OCR_Transaction_History", namespace),
            "APR_AUTO_QUEUE": U.sheet_name("APR_Auto_Queue", namespace),
        }

        for key, actual_name in names.items():
            with st.expander(actual_name, expanded=False):
                st.code(self._header_text(key), language="text")

    def _render_secrets_guide(self) -> None:
        st.subheader("Secrets 形式")

        secrets_text = """[connections.gsheets]
spreadsheet = "YOUR_SPREADSHEET_ID"

[connections.gsheets.credentials]
type = "service_account"
project_id = "..."
private_key_id = "..."
private_key = \"\"\"-----BEGIN PRIVATE KEY-----
...
-----END PRIVATE KEY-----\"\"\"
client_email = "..."
client_id = "..."
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "..."

[ocrspace]
api_key = "..."

[imgbb]
api_key = "..."

[line.tokens]
A = "..."
B = "..."
C = "..."
D = "..."

[admin]
users = [
  { name = "管理者A", pin = "1111", namespace = "A" },
  { name = "管理者B", pin = "2222", namespace = "B" },
  { name = "管理者C", pin = "3333", namespace = "C" },
  { name = "管理者D", pin = "4444", namespace = "D" }
]"""
        st.code(secrets_text, language="toml")

    def _render_usage_steps(self) -> None:
        st.subheader("使い方手順")
        st.markdown(
            """
### 1. 管理者ログイン
- 管理者A〜Dの PIN でログイン
- namespace に応じて `__A / __B / __C / __D` のシートを読みます

### 2. Admin ページ
- Members を管理
- LINE ユーザー紐付け
- 状態切替
- 一括編集
- 個別LINE送信

### 3. Help ページ
- シート構造確認
- 列名確認
- OCR座標確認
- SmartVault OCRテスト
- OCR履歴確認

### 4. APR ページ
- APR を入力
- FinanceEngine で計算
- Ledger 保存
- APR_Summary 保存
- Compound_Timing に応じて daily/monthly/none を反映
- 必要に応じてLINE送信

### 5. Cash ページ
- 入金 / 出金
- Ledger 保存
- Members の Principal 更新
- 必要に応じてLINE送信

### 6. Dashboard
- 総元本
- 本日APR
- APR累計
- SmartVault履歴
- APR履歴
- Ledger最新状況
"""
        )

    def _render_troubleshooting(self) -> None:
        st.subheader("よくあるエラーと対処")
        st.markdown(
            """
### Spreadsheet を開けません
- `connections.gsheets.spreadsheet` が正しいか
- `client_email` を Spreadsheet に共有しているか
- Spreadsheet ID がURLの途中で切れていないか

### Duplicate column names
- シートの1行目に同じ列名が重複していないか
- 列順が定義どおりか

### OCRがうまく読めない
- Settings の OCR 座標が適切か
- 画像が見切れていないか
- 数字の領域が赤枠と一致しているか

### LINEが届かない
- `line.tokens.<namespace>` が正しいか
- `Line_User_ID` が U から始まる正しい値か
- LINE公式アカウントで友だち追加済みか
"""
        )

    def _render_settings_editor(self, settings_df: pd.DataFrame, project: str) -> None:
        st.subheader("Settings 確認 / 保存")

        row = self._project_row(settings_df, project)

        col1, col2 = st.columns(2)

        with col1:
            net_factor = st.number_input(
                "Net_Factor",
                min_value=0.0,
                step=0.01,
                value=self._safe_float(row.get("Net_Factor", 0.67), 0.67),
                key="help_net_factor",
            )

            is_compound = st.selectbox(
                "IsCompound",
                options=["TRUE", "FALSE"],
                index=0 if U.truthy(row.get("IsCompound", False)) else 1,
                key="help_is_compound",
            )

            compound_timing = st.selectbox(
                "Compound_Timing",
                options=[
                    AppConfig.COMPOUND["DAILY"],
                    AppConfig.COMPOUND["MONTHLY"],
                    AppConfig.COMPOUND["NONE"],
                ],
                index=[
                    AppConfig.COMPOUND["DAILY"],
                    AppConfig.COMPOUND["MONTHLY"],
                    AppConfig.COMPOUND["NONE"],
                ].index(U.normalize_compound(row.get("Compound_Timing", AppConfig.COMPOUND["NONE"]))),
                key="help_compound_timing",
            )

            active = st.selectbox(
                "Active",
                options=["TRUE", "FALSE"],
                index=0 if U.truthy(row.get("Active", False)) else 1,
                key="help_active",
            )

        with col2:
            st.caption(f"Project_Name: {project}")
            st.caption(f"UpdatedAt_JST: {self._safe_str(row.get('UpdatedAt_JST', ''))}")

        st.markdown("### SmartVault OCR座標")

        sv1, sv2, sv3, sv4 = st.columns(4)
        with sv1:
            liq_left = st.number_input("SV_Total_Liquidity_Left_Mobile", 0.0, 1.0, self._safe_float(row.get("SV_Total_Liquidity_Left_Mobile", 0.05), 0.05), 0.01, key="sv_liq_left")
            profit_left = st.number_input("SV_Yesterday_Profit_Left_Mobile", 0.0, 1.0, self._safe_float(row.get("SV_Yesterday_Profit_Left_Mobile", 0.40), 0.40), 0.01, key="sv_profit_left")
            apr_left = st.number_input("SV_APR_Left_Mobile", 0.0, 1.0, self._safe_float(row.get("SV_APR_Left_Mobile", 0.70), 0.70), 0.01, key="sv_apr_left")
        with sv2:
            liq_top = st.number_input("SV_Total_Liquidity_Top_Mobile", 0.0, 1.0, self._safe_float(row.get("SV_Total_Liquidity_Top_Mobile", 0.25), 0.25), 0.01, key="sv_liq_top")
            profit_top = st.number_input("SV_Yesterday_Profit_Top_Mobile", 0.0, 1.0, self._safe_float(row.get("SV_Yesterday_Profit_Top_Mobile", 0.25), 0.25), 0.01, key="sv_profit_top")
            apr_top = st.number_input("SV_APR_Top_Mobile", 0.0, 1.0, self._safe_float(row.get("SV_APR_Top_Mobile", 0.25), 0.25), 0.01, key="sv_apr_top")
        with sv3:
            liq_right = st.number_input("SV_Total_Liquidity_Right_Mobile", 0.0, 1.0, self._safe_float(row.get("SV_Total_Liquidity_Right_Mobile", 0.40), 0.40), 0.01, key="sv_liq_right")
            profit_right = st.number_input("SV_Yesterday_Profit_Right_Mobile", 0.0, 1.0, self._safe_float(row.get("SV_Yesterday_Profit_Right_Mobile", 0.70), 0.70), 0.01, key="sv_profit_right")
            apr_right = st.number_input("SV_APR_Right_Mobile", 0.0, 1.0, self._safe_float(row.get("SV_APR_Right_Mobile", 0.95), 0.95), 0.01, key="sv_apr_right")
        with sv4:
            liq_bottom = st.number_input("SV_Total_Liquidity_Bottom_Mobile", 0.0, 1.0, self._safe_float(row.get("SV_Total_Liquidity_Bottom_Mobile", 0.34), 0.34), 0.01, key="sv_liq_bottom")
            profit_bottom = st.number_input("SV_Yesterday_Profit_Bottom_Mobile", 0.0, 1.0, self._safe_float(row.get("SV_Yesterday_Profit_Bottom_Mobile", 0.34), 0.34), 0.01, key="sv_profit_bottom")
            apr_bottom = st.number_input("SV_APR_Bottom_Mobile", 0.0, 1.0, self._safe_float(row.get("SV_APR_Bottom_Mobile", 0.34), 0.34), 0.01, key="sv_apr_bottom")

        st.markdown("### Transaction OCR座標")

        tx1, tx2, tx3 = st.columns(3)
        with tx1:
            tx_scan_base = st.number_input("TX_Scan_BaseTop_Ratio_Mobile", 0.0, 1.0, self._safe_float(row.get("TX_Scan_BaseTop_Ratio_Mobile", 0.0), 0.0), 0.01, key="tx_scan_base")
            tx_date_left = st.number_input("TX_Date_Left_Ratio_Mobile", 0.0, 1.0, self._safe_float(row.get("TX_Date_Left_Ratio_Mobile", 0.0), 0.0), 0.01, key="tx_date_left")
            tx_type_left = st.number_input("TX_Type_Left_Ratio_Mobile", 0.0, 1.0, self._safe_float(row.get("TX_Type_Left_Ratio_Mobile", 0.0), 0.0), 0.01, key="tx_type_left")
            tx_usd_left = st.number_input("TX_USD_Left_Ratio_Mobile", 0.0, 1.0, self._safe_float(row.get("TX_USD_Left_Ratio_Mobile", 0.0), 0.0), 0.01, key="tx_usd_left")
        with tx2:
            tx_scan_step = st.number_input("TX_Scan_Step_Ratio_Mobile", 0.0, 1.0, self._safe_float(row.get("TX_Scan_Step_Ratio_Mobile", 0.0), 0.0), 0.01, key="tx_scan_step")
            tx_date_right = st.number_input("TX_Date_Right_Ratio_Mobile", 0.0, 1.0, self._safe_float(row.get("TX_Date_Right_Ratio_Mobile", 0.0), 0.0), 0.01, key="tx_date_right")
            tx_type_right = st.number_input("TX_Type_Right_Ratio_Mobile", 0.0, 1.0, self._safe_float(row.get("TX_Type_Right_Ratio_Mobile", 0.0), 0.0), 0.01, key="tx_type_right")
            tx_usd_right = st.number_input("TX_USD_Right_Ratio_Mobile", 0.0, 1.0, self._safe_float(row.get("TX_USD_Right_Ratio_Mobile", 0.0), 0.0), 0.01, key="tx_usd_right")
        with tx3:
            tx_scan_max = st.number_input("TX_Scan_MaxRows_Mobile", min_value=0, step=1, value=int(self._safe_float(row.get("TX_Scan_MaxRows_Mobile", 0), 0)), key="tx_scan_max")
            tx_date_top = st.number_input("TX_Date_Top_Offset_Ratio_Mobile", 0.0, 1.0, self._safe_float(row.get("TX_Date_Top_Offset_Ratio_Mobile", 0.0), 0.0), 0.01, key="tx_date_top")
            tx_date_bottom = st.number_input("TX_Date_Bottom_Offset_Ratio_Mobile", 0.0, 1.0, self._safe_float(row.get("TX_Date_Bottom_Offset_Ratio_Mobile", 0.0), 0.0), 0.01, key="tx_date_bottom")
            tx_type_top = st.number_input("TX_Type_Top_Offset_Ratio_Mobile", 0.0, 1.0, self._safe_float(row.get("TX_Type_Top_Offset_Ratio_Mobile", 0.0), 0.0), 0.01, key="tx_type_top")
            tx_type_bottom = st.number_input("TX_Type_Bottom_Offset_Ratio_Mobile", 0.0, 1.0, self._safe_float(row.get("TX_Type_Bottom_Offset_Ratio_Mobile", 0.0), 0.0), 0.01, key="tx_type_bottom")
            tx_usd_top = st.number_input("TX_USD_Top_Offset_Ratio_Mobile", 0.0, 1.0, self._safe_float(row.get("TX_USD_Top_Offset_Ratio_Mobile", 0.0), 0.0), 0.01, key="tx_usd_top")
            tx_usd_bottom = st.number_input("TX_USD_Bottom_Offset_Ratio_Mobile", 0.0, 1.0, self._safe_float(row.get("TX_USD_Bottom_Offset_Ratio_Mobile", 0.0), 0.0), 0.01, key="tx_usd_bottom")

        if st.button("Settings を保存", use_container_width=True, key="help_save_settings"):
            updates = {
                "Net_Factor": net_factor,
                "IsCompound": is_compound,
                "Compound_Timing": compound_timing,
                "Active": active,
                "SV_Total_Liquidity_Left_Mobile": liq_left,
                "SV_Total_Liquidity_Top_Mobile": liq_top,
                "SV_Total_Liquidity_Right_Mobile": liq_right,
                "SV_Total_Liquidity_Bottom_Mobile": liq_bottom,
                "SV_Yesterday_Profit_Left_Mobile": profit_left,
                "SV_Yesterday_Profit_Top_Mobile": profit_top,
                "SV_Yesterday_Profit_Right_Mobile": profit_right,
                "SV_Yesterday_Profit_Bottom_Mobile": profit_bottom,
                "SV_APR_Left_Mobile": apr_left,
                "SV_APR_Top_Mobile": apr_top,
                "SV_APR_Right_Mobile": apr_right,
                "SV_APR_Bottom_Mobile": apr_bottom,
                "TX_Scan_BaseTop_Ratio_Mobile": tx_scan_base,
                "TX_Scan_Step_Ratio_Mobile": tx_scan_step,
                "TX_Scan_MaxRows_Mobile": tx_scan_max,
                "TX_Date_Left_Ratio_Mobile": tx_date_left,
                "TX_Date_Right_Ratio_Mobile": tx_date_right,
                "TX_Date_Top_Offset_Ratio_Mobile": tx_date_top,
                "TX_Date_Bottom_Offset_Ratio_Mobile": tx_date_bottom,
                "TX_Type_Left_Ratio_Mobile": tx_type_left,
                "TX_Type_Right_Ratio_Mobile": tx_type_right,
                "TX_Type_Top_Offset_Ratio_Mobile": tx_type_top,
                "TX_Type_Bottom_Offset_Ratio_Mobile": tx_type_bottom,
                "TX_USD_Left_Ratio_Mobile": tx_usd_left,
                "TX_USD_Right_Ratio_Mobile": tx_usd_right,
                "TX_USD_Top_Offset_Ratio_Mobile": tx_usd_top,
                "TX_USD_Bottom_Offset_Ratio_Mobile": tx_usd_bottom,
            }
            self._save_settings_row(settings_df, project, updates)
            st.success("Settings を保存しました。")
            st.rerun()

    def _render_ocr_test(self, settings_df: pd.DataFrame, project: str) -> None:
        st.subheader("SmartVault OCRテスト")

        row = self._project_row(settings_df, project)
        boxes = self._smartvault_boxes_from_row(row)

        uploaded = st.file_uploader("画像", type=["png", "jpg", "jpeg"], key="help_ocr_file")
        if not uploaded:
            st.info("画像を選択すると OCR テストを実行します。")
            return

        img = Image.open(uploaded).convert("RGB")
        st.image(self._draw_boxes(img.copy(), boxes), caption="OCR範囲", use_container_width=True)

        results = {}
        for key, b in boxes.items():
            crop = self._crop(img, b)
            buf = io.BytesIO()
            crop.save(buf, format="PNG")

            txt = ExternalService.ocr_space_extract_text(buf.getvalue())
            results[key] = {
                "text": txt,
                "value": self._num(txt),
            }

        c1, c2, c3 = st.columns(3)
        c1.metric("Liquidity", f"{results['LIQUIDITY']['value']}")
        c2.metric("Yesterday Profit", f"{results['YESTERDAY_PROFIT']['value']}")
        c3.metric("APR", f"{results['APR']['value']}")

        st.text_area("OCR RAW", str(results), height=220)

    def _render_history(self) -> None:
        st.subheader("OCR Transaction History（先頭30件）")
        ocr_hist = self.repo.load_ocr_transaction_history()
        ocr_hist = self._safe_df(ocr_hist)

        if ocr_hist.empty:
            st.info("OCR_Transaction_History は空です。")
        else:
            st.dataframe(ocr_hist.head(30), use_container_width=True, hide_index=True)

        st.subheader("APR Auto Queue（先頭30件）")
        queue_df = self.repo.load_apr_auto_queue()
        queue_df = self._safe_df(queue_df)

        if queue_df.empty:
            st.info("APR_Auto_Queue は空です。")
        else:
            st.dataframe(queue_df.head(30), use_container_width=True, hide_index=True)

    def render(self) -> None:
        st.title("ヘルプ / OCR設定 / 運用マニュアル")
        namespace = AdminAuth.current_namespace()
        st.caption(f"管理者: {namespace}")

        settings_df = self._safe_df(self.repo.load_settings())
        projects = self.repo.active_projects(settings_df)

        tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
            [
                "概要",
                "シート / 列名",
                "Secrets",
                "使い方",
                "Settings / OCR調整",
                "履歴",
            ]
        )

        with tab1:
            self._render_overview(namespace)
            self._render_troubleshooting()

        with tab2:
            self._render_sheet_columns(namespace)

        with tab3:
            self._render_secrets_guide()

        with tab4:
            self._render_usage_steps()

        with tab5:
            if not projects:
                st.warning("有効なプロジェクトがありません。")
            else:
                project = st.selectbox("対象プロジェクト", projects, key="help_project")
                self._render_settings_editor(settings_df, project)
                st.divider()
                self._render_ocr_test(settings_df, project)

        with tab6:
            self._render_history()


# END OF FILE
