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

    OCR_HISTORY_SHEET = "OCR_Transaction_History"

    def __init__(self, repo: Repository, store: DataStore):
        self.repo = repo
        self.store = store


    def render(self, gs: GSheetService, settings_df: pd.DataFrame):

        st.subheader("❓ 操作マニュアル / ヘルプ")
        st.caption(f"{AppConfig.RANK_LABEL} / 管理者: {AdminAuth.current_label()}")


        st.markdown("""
このページでは **アプリの設定方法 / OCR調整 / シート構造 / APIキー取得場所** を説明します。

変更は基本的に **コードではなくシートかSecretsで行う設計**です。
""")


        # --------------------------------------------------------
        # 接続情報
        # --------------------------------------------------------

        with st.expander("接続情報"):

            st.code(f"""
Settings = {gs.names.SETTINGS}
Members = {gs.names.MEMBERS}
Ledger = {gs.names.LEDGER}
LineUsers = {gs.names.LINEUSERS}

Spreadsheet ID
{gs.spreadsheet_id}

Spreadsheet URL
{gs.spreadsheet_url()}
""")


        # --------------------------------------------------------
        # 外部サービス
        # --------------------------------------------------------

        with st.expander("APIキー取得先"):

            st.markdown("""
Google Cloud  
https://console.cloud.google.com

Google Sheets  
https://docs.google.com/spreadsheets

LINE Developers  
https://developers.line.biz/console

OCR.space  
https://ocr.space/ocrapi

ImgBB  
https://api.imgbb.com
""")


        # --------------------------------------------------------
        # Secrets
        # --------------------------------------------------------

        with st.expander("Secrets 設定例"):

            st.code("""
[connections.gsheets]
spreadsheet = "YOUR_SPREADSHEET_ID"

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
api_key = "OCR_SPACE_API_KEY"
""")


        # --------------------------------------------------------
        # シート構造
        # --------------------------------------------------------

        with st.expander("シート構造"):

            st.markdown("Settings")

            st.code("\t".join(AppConfig.HEADERS["SETTINGS"]))

            st.markdown("Members")

            st.code("\t".join(AppConfig.HEADERS["MEMBERS"]))

            st.markdown("Ledger")

            st.code("\t".join(AppConfig.HEADERS["LEDGER"]))


        # --------------------------------------------------------
        # OCR設定
        # --------------------------------------------------------

        with st.expander("OCR座標設定"):

            projects = self.repo.active_projects(settings_df)

            if not projects:

                st.warning("Activeプロジェクトがありません")

                return

            project = st.selectbox(
                "プロジェクト",
                projects
            )

            row = settings_df[
                settings_df["Project_Name"] == project
            ].iloc[0]


            st.markdown("### 現在の設定")

            st.dataframe(
                pd.DataFrame([row]),
                use_container_width=True
            )


            # -------------------------
            # PC
            # -------------------------

            st.markdown("### PC")

            c1,c2,c3,c4 = st.columns(4)

            pc_left = c1.number_input(
                "Left",
                0.0,1.0,
                float(row["Crop_Left_Ratio_PC"]),
                0.01
            )

            pc_top = c2.number_input(
                "Top",
                0.0,1.0,
                float(row["Crop_Top_Ratio_PC"]),
                0.01
            )

            pc_right = c3.number_input(
                "Right",
                0.0,1.0,
                float(row["Crop_Right_Ratio_PC"]),
                0.01
            )

            pc_bottom = c4.number_input(
                "Bottom",
                0.0,1.0,
                float(row["Crop_Bottom_Ratio_PC"]),
                0.01
            )


            # -------------------------
            # Mobile
            # -------------------------

            st.markdown("### Mobile")

            c5,c6,c7,c8 = st.columns(4)

            mobile_left = c5.number_input(
                "Left ",
                0.0,1.0,
                float(row["Crop_Left_Ratio_Mobile"]),
                0.01
            )

            mobile_top = c6.number_input(
                "Top ",
                0.0,1.0,
                float(row["Crop_Top_Ratio_Mobile"]),
                0.01
            )

            mobile_right = c7.number_input(
                "Right ",
                0.0,1.0,
                float(row["Crop_Right_Ratio_Mobile"]),
                0.01
            )

            mobile_bottom = c8.number_input(
                "Bottom ",
                0.0,1.0,
                float(row["Crop_Bottom_Ratio_Mobile"]),
                0.01
            )


            # --------------------------------------------------
            # 画像アップロード
            # --------------------------------------------------

            st.markdown("### OCR確認")

            img = st.file_uploader(
                "画像をアップロード",
                type=["png","jpg","jpeg"]
            )


            if img:

                file_bytes = img.getvalue()

                st.markdown("元画像")

                st.image(
                    file_bytes,
                    use_container_width=True
                )


                mobile_box = {
                    "mobile":{
                        "left":mobile_left,
                        "top":mobile_top,
                        "right":mobile_right,
                        "bottom":mobile_bottom
                    }
                }

                pc_box = {
                    "pc":{
                        "left":pc_left,
                        "top":pc_top,
                        "right":pc_right,
                        "bottom":pc_bottom
                    }
                }


                st.markdown("Mobile 赤枠")

                st.image(
                    U.draw_ocr_boxes(file_bytes,mobile_box),
                    use_container_width=True
                )


                st.markdown("PC 赤枠")

                st.image(
                    U.draw_ocr_boxes(file_bytes,pc_box),
                    use_container_width=True
                )


            # --------------------------------------------------
            # 保存
            # --------------------------------------------------

            if st.button("OCR設定保存"):

                idx = settings_df[
                    settings_df["Project_Name"] == project
                ].index[0]

                settings_df.loc[idx,"Crop_Left_Ratio_PC"] = pc_left
                settings_df.loc[idx,"Crop_Top_Ratio_PC"] = pc_top
                settings_df.loc[idx,"Crop_Right_Ratio_PC"] = pc_right
                settings_df.loc[idx,"Crop_Bottom_Ratio_PC"] = pc_bottom

                settings_df.loc[idx,"Crop_Left_Ratio_Mobile"] = mobile_left
                settings_df.loc[idx,"Crop_Top_Ratio_Mobile"] = mobile_top
                settings_df.loc[idx,"Crop_Right_Ratio_Mobile"] = mobile_right
                settings_df.loc[idx,"Crop_Bottom_Ratio_Mobile"] = mobile_bottom

                self.repo.write_settings(settings_df)

                self.store.persist_and_refresh()

                st.success("保存しました")

                st.rerun()


        # --------------------------------------------------------
        # 修復
        # --------------------------------------------------------

        with st.expander("Settings修復"):

            if st.button("自動修復"):

                self.repo.repair_settings(
                    self.repo.load_settings()
                )

                self.store.persist_and_refresh()

                st.success("修復しました")

                st.rerun()


        st.success("ヘルプページ読み込み完了")
