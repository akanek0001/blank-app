from __future__ import annotations

import io
import re
from typing import Dict

import pandas as pd
import streamlit as st
from PIL import Image, ImageDraw

from config import AppConfig
from repository.repository import Repository
from services.external_service import ExternalService


class HelpPage:
    def __init__(self, repo: Repository):
        self.repo = repo

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

    def _num(self, text: str) -> float:
        m = re.findall(r"[-+]?\d*\.\d+|\d+", str(text).replace(",", ""))
        return float(m[0]) if m else 0.0

    def _crop(self, img: Image.Image, box: Dict[str, float]) -> Image.Image:
        w, h = img.size
        return img.crop((int(box["left"] * w), int(box["top"] * h), int(box["right"] * w), int(box["bottom"] * h)))

    def _draw_boxes(self, img: Image.Image, boxes: Dict[str, Dict[str, float]]) -> Image.Image:
        d = ImageDraw.Draw(img)
        w, h = img.size
        for _, b in boxes.items():
            d.rectangle([(b["left"] * w, b["top"] * h), (b["right"] * w, b["bottom"] * h)], outline="red", width=3)
        return img

    def _project_row(self, settings_df: pd.DataFrame, project: str) -> pd.Series:
        sdf = settings_df.copy()
        sdf["Project_Name"] = sdf["Project_Name"].astype(str).str.strip()
        return sdf[sdf["Project_Name"] == str(project).strip()].iloc[0]

    def _header_text(self, key: str) -> str:
        return "\n".join(AppConfig.HEADERS[key])

    def render(self) -> None:
        st.subheader("ヘルプ / OCR設定 / 運用マニュアル")
        settings_df = self._safe_df(self.repo.load_settings())
        projects = self.repo.active_projects(settings_df)

        tab1, tab2, tab3, tab4, tab5 = st.tabs(["概要", "シート/列名", "Secrets", "Settings/OCR調整", "履歴"])

        with tab1:
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

## シート構造（完全固定）
- {AppConfig.SHEET['SETTINGS']}
- {AppConfig.SHEET['MEMBERS']}
- {AppConfig.SHEET['LEDGER']}
- {AppConfig.SHEET['LINEUSERS']}
- {AppConfig.SHEET['APR_SUMMARY']}
- {AppConfig.SHEET['SMARTVAULT_HISTORY']}
- {AppConfig.SHEET['OCR_TRANSACTION']}
- {AppConfig.SHEET['OCR_TRANSACTION_HISTORY']}
- {AppConfig.SHEET['APR_AUTO_QUEUE']}

## コア責務
1. UIは計算しない  
2. Repositoryはロジックを持たない  
3. Engineだけが計算する  
4. Serviceは外部接続だけ  
5. Controllerが全部をつなぐ

## 計算ロジック
- Master = 0.67
- Elite = 0.60
- PERSONAL: Principal × APR ÷ 100 × Rank係数 ÷ 365
- GROUP: 総元本 × APR ÷ 100 × Net_Factor ÷ 365 ÷ 人数
- Compound_Timing: daily / monthly / none
"""
            )

        with tab2:
            for key, actual in AppConfig.SHEET.items():
                with st.expander(actual, expanded=False):
                    st.code(self._header_text(key), language="text")

        with tab3:
            st.code(
                """[connections.gsheets]
spreadsheet = \"YOUR_SPREADSHEET_ID\"

[connections.gsheets.credentials]
type = \"service_account\"
project_id = \"...\"
private_key_id = \"...\"
private_key = \"\"\"-----BEGIN PRIVATE KEY-----
...
-----END PRIVATE KEY-----\"\"\"
client_email = \"...\"
client_id = \"...\"
auth_uri = \"https://accounts.google.com/o/oauth2/auth\"
token_uri = \"https://oauth2.googleapis.com/token\"
auth_provider_x509_cert_url = \"https://www.googleapis.com/oauth2/v1/certs\"
client_x509_cert_url = \"...\"

[ocrspace]
api_key = \"...\"

[imgbb]
api_key = \"...\"

[line.tokens]
A = \"...\""" , language="toml"
            )
            st.markdown("- サービスアカウントの client_email を対象 Spreadsheet に編集者権限で共有してください。")

        with tab4:
            if not projects:
                st.warning("有効なプロジェクトがありません。")
            else:
                project = st.selectbox("対象プロジェクト", projects, key="help_project")
                row = self._project_row(settings_df, project)

                st.markdown("### 基本設定")
                col1, col2 = st.columns(2)
                with col1:
                    net_factor = st.number_input("Net_Factor", min_value=0.0, step=0.01, value=self._safe_float(row.get("Net_Factor", 0.67), 0.67))
                    is_compound = st.selectbox("IsCompound", ["TRUE", "FALSE"], index=0 if str(row.get("IsCompound", "")).lower() in {"true", "1", "yes", "on"} else 1)
                    compound_timing = st.selectbox("Compound_Timing", ["daily", "monthly", "none"], index=["daily", "monthly", "none"].index(str(row.get("Compound_Timing", "none")).lower() if str(row.get("Compound_Timing", "none")).lower() in {"daily","monthly","none"} else "none"))
                    active = st.selectbox("Active", ["TRUE", "FALSE"], index=0 if str(row.get("Active", "")).lower() in {"true", "1", "yes", "on"} else 1)
                with col2:
                    st.caption(f"Project_Name: {project}")
                    st.caption(f"UpdatedAt_JST: {str(row.get('UpdatedAt_JST', ''))}")

                st.markdown("### SmartVault OCR座標")
                c1, c2, c3, c4 = st.columns(4)
                with c1:
                    liq_left = st.number_input("SV_Total_Liquidity_Left_Mobile", 0.0, 1.0, self._safe_float(row.get("SV_Total_Liquidity_Left_Mobile", 0.05), 0.05), 0.01)
                    profit_left = st.number_input("SV_Yesterday_Profit_Left_Mobile", 0.0, 1.0, self._safe_float(row.get("SV_Yesterday_Profit_Left_Mobile", 0.40), 0.40), 0.01)
                    apr_left = st.number_input("SV_APR_Left_Mobile", 0.0, 1.0, self._safe_float(row.get("SV_APR_Left_Mobile", 0.70), 0.70), 0.01)
                with c2:
                    liq_top = st.number_input("SV_Total_Liquidity_Top_Mobile", 0.0, 1.0, self._safe_float(row.get("SV_Total_Liquidity_Top_Mobile", 0.25), 0.25), 0.01)
                    profit_top = st.number_input("SV_Yesterday_Profit_Top_Mobile", 0.0, 1.0, self._safe_float(row.get("SV_Yesterday_Profit_Top_Mobile", 0.25), 0.25), 0.01)
                    apr_top = st.number_input("SV_APR_Top_Mobile", 0.0, 1.0, self._safe_float(row.get("SV_APR_Top_Mobile", 0.25), 0.25), 0.01)
                with c3:
                    liq_right = st.number_input("SV_Total_Liquidity_Right_Mobile", 0.0, 1.0, self._safe_float(row.get("SV_Total_Liquidity_Right_Mobile", 0.40), 0.40), 0.01)
                    profit_right = st.number_input("SV_Yesterday_Profit_Right_Mobile", 0.0, 1.0, self._safe_float(row.get("SV_Yesterday_Profit_Right_Mobile", 0.70), 0.70), 0.01)
                    apr_right = st.number_input("SV_APR_Right_Mobile", 0.0, 1.0, self._safe_float(row.get("SV_APR_Right_Mobile", 0.95), 0.95), 0.01)
                with c4:
                    liq_bottom = st.number_input("SV_Total_Liquidity_Bottom_Mobile", 0.0, 1.0, self._safe_float(row.get("SV_Total_Liquidity_Bottom_Mobile", 0.34), 0.34), 0.01)
                    profit_bottom = st.number_input("SV_Yesterday_Profit_Bottom_Mobile", 0.0, 1.0, self._safe_float(row.get("SV_Yesterday_Profit_Bottom_Mobile", 0.34), 0.34), 0.01)
                    apr_bottom = st.number_input("SV_APR_Bottom_Mobile", 0.0, 1.0, self._safe_float(row.get("SV_APR_Bottom_Mobile", 0.34), 0.34), 0.01)

                if st.button("Settings を保存", use_container_width=True):
                    sdf = settings_df.copy()
                    sdf["Project_Name"] = sdf["Project_Name"].astype(str).str.strip()
                    mask = sdf["Project_Name"] == str(project).strip()
                    sdf.loc[mask, "Net_Factor"] = net_factor
                    sdf.loc[mask, "IsCompound"] = is_compound
                    sdf.loc[mask, "Compound_Timing"] = compound_timing
                    sdf.loc[mask, "Active"] = active
                    sdf.loc[mask, "SV_Total_Liquidity_Left_Mobile"] = liq_left
                    sdf.loc[mask, "SV_Total_Liquidity_Top_Mobile"] = liq_top
                    sdf.loc[mask, "SV_Total_Liquidity_Right_Mobile"] = liq_right
                    sdf.loc[mask, "SV_Total_Liquidity_Bottom_Mobile"] = liq_bottom
                    sdf.loc[mask, "SV_Yesterday_Profit_Left_Mobile"] = profit_left
                    sdf.loc[mask, "SV_Yesterday_Profit_Top_Mobile"] = profit_top
                    sdf.loc[mask, "SV_Yesterday_Profit_Right_Mobile"] = profit_right
                    sdf.loc[mask, "SV_Yesterday_Profit_Bottom_Mobile"] = profit_bottom
                    sdf.loc[mask, "SV_APR_Left_Mobile"] = apr_left
                    sdf.loc[mask, "SV_APR_Top_Mobile"] = apr_top
                    sdf.loc[mask, "SV_APR_Right_Mobile"] = apr_right
                    sdf.loc[mask, "SV_APR_Bottom_Mobile"] = apr_bottom
                    sdf.loc[mask, "UpdatedAt_JST"] = pd.Timestamp.now(tz="Asia/Tokyo").strftime("%Y-%m-%d %H:%M:%S")
                    self.repo.write_settings(sdf)
                    st.success("Settings を保存しました。")
                    st.rerun()

                st.markdown("### SmartVault OCRテスト")
                uploaded = st.file_uploader("画像", type=["png", "jpg", "jpeg"], key="help_ocr_file")
                if uploaded:
                    boxes = {
                        "LIQUIDITY": {"left": liq_left, "top": liq_top, "right": liq_right, "bottom": liq_bottom},
                        "YESTERDAY_PROFIT": {"left": profit_left, "top": profit_top, "right": profit_right, "bottom": profit_bottom},
                        "APR": {"left": apr_left, "top": apr_top, "right": apr_right, "bottom": apr_bottom},
                    }
                    img = Image.open(uploaded).convert("RGB")
                    st.image(self._draw_boxes(img.copy(), boxes), caption="OCR範囲", use_container_width=True)
                    results = {}
                    for key, b in boxes.items():
                        crop = self._crop(img, b)
                        buf = io.BytesIO()
                        crop.save(buf, format="PNG")
                        txt = ExternalService.ocr_space_extract_text(buf.getvalue())
                        results[key] = {"text": txt, "value": self._num(txt)}
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Liquidity", f"{results['LIQUIDITY']['value']}")
                    c2.metric("Yesterday Profit", f"{results['YESTERDAY_PROFIT']['value']}")
                    c3.metric("APR", f"{results['APR']['value']}")
                    st.text_area("OCR RAW", str(results), height=220)

        with tab5:
            st.subheader("OCR Transaction History（先頭30件）")
            ocr_hist = self._safe_df(self.repo.load_ocr_transaction_history())
            if ocr_hist.empty:
                st.info("OCR_Transaction_History は空です。")
            else:
                st.dataframe(ocr_hist.head(30), use_container_width=True, hide_index=True)

            st.subheader("APR Auto Queue（先頭30件）")
            queue_df = self._safe_df(self.repo.load_apr_auto_queue())
            if queue_df.empty:
                st.info("APR_Auto_Queue は空です。")
            else:
                st.dataframe(queue_df.head(30), use_container_width=True, hide_index=True)
