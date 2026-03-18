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

    def render(self, gs: GSheetService, settings_df: pd.DataFrame) -> None:
        st.subheader("❓ ヘルプ / 設定ガイド")
        st.caption(f"{AppConfig.RANK_LABEL} / 管理者: {AdminAuth.current_label()}")

        st.markdown(
            """
このページでは、このアプリの **設定変更箇所 / APIキー取得先 / シート構成 / OCR設定 / 重複防止 / トラブル対応** をまとめています。

このアプリは、できるだけ **コードを変更せずに設定変更だけで運用を変えられる** ようにしています。  
主な変更箇所は次のとおりです。

1. **Secrets**  
   Google Sheets接続 / 管理者ログイン / LINE token / APIキー / ローカル監視フォルダ

2. **Settingsシート**  
   プロジェクト設定 / 複利設定 / OCR座標 / 運用ON/OFF

3. **Membersシート**  
   個人名 / 元本 / Rank / LINE送信先 / 運用ON/OFF

4. **OCR_Transaction_Historyシート**  
   受け取ったUSDC等の OCR取引履歴 / 重複防止

5. **このヘルプページ**  
   どこを変えると何が変わるかの確認
"""
        )

        with st.expander("1. 現在の接続情報", expanded=False):
            st.code(
                f"""参照シート
Settings                = {gs.names.SETTINGS}
Members                 = {gs.names.MEMBERS}
Ledger                  = {gs.names.LEDGER}
LineUsers               = {gs.names.LINEUSERS}
APR_Summary             = {gs.names.APR_SUMMARY}
SmartVault_History      = {gs.names.SMARTVAULT_HISTORY}
OCR_Transaction_History = {self.OCR_TX_HISTORY_SHEET}

Spreadsheet ID
{gs.spreadsheet_id}

Spreadsheet URL
{gs.spreadsheet_url()}
"""
            )

        with st.expander("2. 変更箇所の全体像", expanded=False):
            st.markdown(
                """
### Secrets で変えるもの
- Google Sheets接続
- 管理者PIN
- 管理者ごとの namespace
- 管理者ごとの LINE token
- ImgBB API key
- OCR.space API key
- ローカル監視フォルダパス

### Settingsシートで変えるもの
- Project_Name
- Net_Factor
- IsCompound
- Compound_Timing
- OCR座標
- Active

### Membersシートで変えるもの
- PersonName
- Principal
- Line_User_ID
- LINE_DisplayName
- Rank
- IsActive

### OCR_Transaction_History シートで確認するもの
- OCRで拾った取引履歴
- 重複判定キー
- 元画像名
- OCR生テキスト
"""
            )

        with st.expander("3. APIキー取得URL / 外部サービスURL", expanded=False):
            st.markdown(
                """
### Google Cloud Console
Google Sheets API とサービスアカウントJSONを作成する場所

```text
https://console.cloud.google.com/
```

### Google Sheets
運用で使うスプレッドシート

```text
https://docs.google.com/spreadsheets/
```

### LINE Developers Console
Messaging API チャンネル作成 / Channel Access Token 取得

```text
https://developers.line.biz/console/
```

### LINE Messaging API ドキュメント
LINE User ID / Messaging API の確認

```text
https://developers.line.biz/en/docs/messaging-api/
```

### OCR.space
OCR APIキー取得

```text
https://ocr.space/ocrapi
```

### ImgBB
画像アップロード APIキー取得

```text
https://api.imgbb.com/
```

### Streamlit Community Cloud
Secrets 設定画面

```text
https://share.streamlit.io/
```
"""
            )

        with st.expander("4. Secrets 設定例", expanded=False):
            st.markdown("### Secrets に貼る内容の例")
            st.code(
                """[connections.gsheets]
spreadsheet = "ここにSpreadsheet ID"

[connections.gsheets.credentials]
type = "service_account"
project_id = "ここにproject_id"
private_key_id = "ここにprivate_key_id"
private_key = \"\"\"-----BEGIN PRIVATE KEY-----
ここにprivate_key
-----END PRIVATE KEY-----\"\"\"
client_email = "ここにclient_email"
client_id = "ここにclient_id"
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "ここにclient_x509_cert_url"
universe_domain = "googleapis.com"

[admin]
pin = "ここに共通PIN"

[[admin.users]]
name = "Admin A"
pin = "1111"
namespace = "A"

[[admin.users]]
name = "Admin B"
pin = "2222"
namespace = "B"

[[admin.users]]
name = "Admin C"
pin = "3333"
namespace = "C"

[[admin.users]]
name = "Admin D"
pin = "4444"
namespace = "D"

[line.tokens]
A = "ここにAのLINEトークン"
B = "ここにBのLINEトークン"
C = "ここにCのLINEトークン"
D = "ここにDのLINEトークン"

[imgbb]
api_key = "ここにImgBB APIキー"

[ocrspace]
api_key = "ここにOCR.space APIキー"

[local_paths]
apr_watch_folder = "/Users/あなたのユーザー名/Desktop/smartvault_images"
"""
            )

            st.markdown(
                """
### 各項目の意味
- `spreadsheet`  
  Google Sheets の Spreadsheet ID

- `credentials`  
  GoogleサービスアカウントJSONの内容

- `[[admin.users]]`  
  管理者ごとのログイン情報

- `namespace`  
  管理者ごとに使用シート名・LINE token を分ける識別子

- `[line.tokens]`  
  namespace に対応する LINE Channel Access Token

- `[imgbb]`  
  画像アップロード用 APIキー

- `[ocrspace]`  
  OCR用 APIキー

- `[local_paths].apr_watch_folder`  
  ローカルで画像を自動OCRしたいときの監視フォルダ
"""
            )

        with st.expander("5. シート構成", expanded=False):
            st.markdown("### Settings")
            st.code("\t".join(AppConfig.HEADERS["SETTINGS"]))

            st.markdown("### Members")
            st.code("\t".join(AppConfig.HEADERS["MEMBERS"]))

            st.markdown("### Ledger")
            st.code("\t".join(AppConfig.HEADERS["LEDGER"]))

            st.markdown("### LineUsers")
            st.code("\t".join(AppConfig.HEADERS["LINEUSERS"]))

            st.markdown("### APR Summary")
            st.code("\t".join(AppConfig.HEADERS["APR_SUMMARY"]))

            st.markdown("### SmartVault_History")
            st.code("\t".join(AppConfig.HEADERS["SMARTVAULT_HISTORY"]))

            st.markdown("### OCR_Transaction_History")
            st.code("\t".join(self.OCR_TX_HISTORY_HEADERS))

        with st.expander("6. Settingsシートで変える項目", expanded=False):
            st.markdown(
                """
### 主要項目
- `Project_Name`  
  プロジェクト名

- `Net_Factor`  
  GROUP計算時の係数

- `IsCompound`  
  複利計算するかどうか

- `Compound_Timing`  
  `daily / monthly / none`

- `Active`  
  このプロジェクトを運用対象にするか

- `Crop_Left_Ratio_PC` など  
  OCR切り抜き座標
"""
            )

            st.markdown("### 将来の汎用化で追加推奨の列")
            st.code(
                "Calc_Mode\tEnable_LINE_Send\tEnable_OCR\tEnable_Evidence_Image\t"
                "Line_Message_Template\tCurrency\tAPR_Decimals\tPrincipal_Decimals\t"
                "Group_Distribution_Mode\tDefault_Rank\tProject_Display_Name\tAdmin_Memo\tSort_Order"
            )

        with st.expander("7. Membersシートで変える項目", expanded=False):
            st.markdown(
                """
### 主要項目
- `Project_Name`  
  所属プロジェクト

- `PersonName`  
  個人名

- `Principal`  
  元本

- `Line_User_ID`  
  LINE送信先ID

- `LINE_DisplayName`  
  管理画面や履歴で使う表示名

- `Rank`  
  `Master / Elite`

- `IsActive`  
  運用対象かどうか
"""
            )

            st.markdown("### 将来の汎用化で追加推奨の列")
            st.code(
                "Personal_Net_Factor\tCustom_Compound_Timing\tLine_Send_Enabled\tRole\t"
                "Memo\tSort_Order\tDisplay_Group\tPrincipal_Visible\tCustom_Line_Name"
            )

        with st.expander("8. OCR_Transaction_History シート", expanded=False):
            st.markdown(
                """
### シート名
```text
OCR_Transaction_History
```

### 項目名（そのままコピー＆ペースト用）
"""
            )
            st.code("\t".join(self.OCR_TX_HISTORY_HEADERS))

            st.markdown(
                """
### 各列の意味
- `Unique_Key`  
  重複判定キー

- `Date_Label`  
  OCRで読んだ日付表示

- `Time_Label`  
  OCRで読んだ時刻表示

- `Type_Label`  
  `受け取ったUSDC` などの種別

- `Amount_USD`  
  `$112.68` のようなUSD金額

- `Token_Amount`  
  受け取った数量

- `Token_Symbol`  
  `USDC / ETH / BTC / USDT` など

- `Source_Image`  
  元画像ファイル名

- `Source_Project`  
  そのとき選んでいたプロジェクト名

- `OCR_Raw_Text`  
  OCR生テキスト

- `CreatedAt_JST`  
  保存日時
"""
            )

        with st.expander("9. OCR重複防止ルール", expanded=False):
            st.markdown(
                """
### 目的
同じ日・同じ時間の画像を複数アップしても、**同じ取引を二重計上しない**ようにします。

### 重複判定キー
内部では次の形式で重複判定します。

```text
Date_Label|Time_Label|Type_Label|Amount_USD
```

### 例
```text
3月18日|10:33 am|受け取ったUSDC|112.68
3月18日|10:09 am|受け取ったUSDC|1.55
```

### この方式で防げるもの
- 同じ画像を再OCR
- 同じ明細が写った別画像
- 同じ日・同じ時間帯の重複集計

### 集計対象の考え方
- `$金額がある`
- `受け取ったUSDC` など受取系の明細
- `$0.00` や承認系は除外
"""
            )

        with st.expander("10. Compound_Timing の意味", expanded=False):
            st.markdown(
                """
- `daily`  
  APR確定時に元本へ即時加算します。次回以降は増えた元本で計算します。

- `monthly`  
  APR確定時は Ledger に記録のみ行います。元本への反映は APR画面の「未反映APRを元本へ反映」でまとめて行います。

- `none`  
  単利です。APRは Ledger に記録しますが、元本には加算しません。
"""
            )

        with st.expander("11. APR計算ロジック", expanded=False):
            st.markdown(
                """
### 入力項目
APR画面では以下を管理します。
- 流動性
- 昨日の収益
- APR

いずれも手動入力できます。画像を入れた場合は OCRで別取得 もできます。

### SmartVault履歴
APR確定時に `SmartVault_History` シートへ
- 最終採用値
- OCR取得値
- Source_Mode（manual / ocr / ocr+manual）
を保存します。

### PERSONAL
個人ごとの元本で計算します。

`DailyAPR = Principal × (最終APR% / 100) × Rank係数 ÷ 365`

- Master = 0.67
- Elite = 0.60

### GROUP（PERSONAL以外）
グループ総額を基準に計算し、人数で均等割します。

`グループ総配当 = グループ総元本 × (最終APR% / 100) × Net_Factor ÷ 365`

`1人あたり配当 = グループ総配当 ÷ 人数`

### 重複防止
同日・同一プロジェクト・同一人物の APR は Ledger を見て1回だけ記録します。  
本日のAPRをやり直したい場合は、APR画面の「本日のAPR記録をリセット」を使います。
"""
            )

        with st.expander("12. LINE連携設定", expanded=False):
            st.markdown(
                """
### 必要な設定
1. LINE Developers で Messaging API チャンネル作成  
2. Channel Access Token 発行  
3. Secrets の `[line.tokens]` に保存  
4. Membersシートの `Line_User_ID` に対象ユーザーIDを入れる

### 送信先が決まる仕組み
- ログイン中の管理者 namespace
- `[line.tokens]` の同じ namespace
- Members の `Line_User_ID`

この3つの組み合わせで送信されます。
"""
            )

        with st.expander("13. Make連携", expanded=False):
            st.markdown(
                """
### 目的
LINEユーザー情報を `LineUsers` シートへ自動登録し、管理画面の追加候補として使います。

### 推奨フロー
`LINE Watch Events → HTTP(プロフィール取得) → Google Sheets Search Rows → Filter(0件のみ) → Google Sheets Add a Row`
"""
            )
            st.code("\t".join(AppConfig.HEADERS["LINEUSERS"]))

        with st.expander("14. OCR設定（座標設定 + 赤枠プレビュー）", expanded=False):
            projects = self.repo.active_projects(settings_df)
            if not projects:
                st.warning("有効なプロジェクトがありません。")
            else:
                ocr_project = st.selectbox("OCR設定対象プロジェクト", projects, key="help_ocr_project")
                row_setting = settings_df[settings_df["Project_Name"] == ocr_project].iloc[0]

                st.markdown("#### 現在値")
                current_vals = pd.DataFrame(
                    [
                        {
                            "Crop_Left_Ratio_PC": row_setting.get(
                                "Crop_Left_Ratio_PC",
                                AppConfig.OCR_DEFAULTS_PC["Crop_Left_Ratio_PC"],
                            ),
                            "Crop_Top_Ratio_PC": row_setting.get(
                                "Crop_Top_Ratio_PC",
                                AppConfig.OCR_DEFAULTS_PC["Crop_Top_Ratio_PC"],
                            ),
                            "Crop_Right_Ratio_PC": row_setting.get(
                                "Crop_Right_Ratio_PC",
                                AppConfig.OCR_DEFAULTS_PC["Crop_Right_Ratio_PC"],
                            ),
                            "Crop_Bottom_Ratio_PC": row_setting.get(
                                "Crop_Bottom_Ratio_PC",
                                AppConfig.OCR_DEFAULTS_PC["Crop_Bottom_Ratio_PC"],
                            ),
                            "Crop_Left_Ratio_Mobile": row_setting.get(
                                "Crop_Left_Ratio_Mobile",
                                AppConfig.OCR_DEFAULTS_MOBILE["Crop_Left_Ratio_Mobile"],
                            ),
                            "Crop_Top_Ratio_Mobile": row_setting.get(
                                "Crop_Top_Ratio_Mobile",
                                AppConfig.OCR_DEFAULTS_MOBILE["Crop_Top_Ratio_Mobile"],
                            ),
                            "Crop_Right_Ratio_Mobile": row_setting.get(
                                "Crop_Right_Ratio_Mobile",
                                AppConfig.OCR_DEFAULTS_MOBILE["Crop_Right_Ratio_Mobile"],
                            ),
                            "Crop_Bottom_Ratio_Mobile": row_setting.get(
                                "Crop_Bottom_Ratio_Mobile",
                                AppConfig.OCR_DEFAULTS_MOBILE["Crop_Bottom_Ratio_Mobile"],
                            ),
                        }
                    ]
                )
                st.dataframe(current_vals, use_container_width=True, hide_index=True)

                st.markdown("#### SmartVaultモバイル専用 固定赤枠座標")
                st.code(
                    f"""TOTAL_LIQUIDITY
left={AppConfig.SMARTVAULT_BOXES_MOBILE['TOTAL_LIQUIDITY']['left']:.2f}
top={AppConfig.SMARTVAULT_BOXES_MOBILE['TOTAL_LIQUIDITY']['top']:.2f}
right={AppConfig.SMARTVAULT_BOXES_MOBILE['TOTAL_LIQUIDITY']['right']:.2f}
bottom={AppConfig.SMARTVAULT_BOXES_MOBILE['TOTAL_LIQUIDITY']['bottom']:.2f}

YESTERDAY_PROFIT
left={AppConfig.SMARTVAULT_BOXES_MOBILE['YESTERDAY_PROFIT']['left']:.2f}
top={AppConfig.SMARTVAULT_BOXES_MOBILE['YESTERDAY_PROFIT']['top']:.2f}
right={AppConfig.SMARTVAULT_BOXES_MOBILE['YESTERDAY_PROFIT']['right']:.2f}
bottom={AppConfig.SMARTVAULT_BOXES_MOBILE['YESTERDAY_PROFIT']['bottom']:.2f}

APR
left={AppConfig.SMARTVAULT_BOXES_MOBILE['APR']['left']:.2f}
top={AppConfig.SMARTVAULT_BOXES_MOBILE['APR']['top']:.2f}
right={AppConfig.SMARTVAULT_BOXES_MOBILE['APR']['right']:.2f}
bottom={AppConfig.SMARTVAULT_BOXES_MOBILE['APR']['bottom']:.2f}
"""
                )

                st.markdown("#### 座標入力")

                st.markdown("##### PC")
                c1, c2, c3, c4 = st.columns(4)
                pc_left = c1.number_input(
                    "Crop_Left_Ratio_PC",
                    min_value=0.0,
                    max_value=1.0,
                    value=float(
                        row_setting.get(
                            "Crop_Left_Ratio_PC",
                            AppConfig.OCR_DEFAULTS_PC["Crop_Left_Ratio_PC"],
                        )
                    ),
                    step=0.01,
                    key=f"help_pc_left_{ocr_project}",
                )
                pc_top = c2.number_input(
                    "Crop_Top_Ratio_PC",
                    min_value=0.0,
                    max_value=1.0,
                    value=float(
                        row_setting.get(
                            "Crop_Top_Ratio_PC",
                            AppConfig.OCR_DEFAULTS_PC["Crop_Top_Ratio_PC"],
                        )
                    ),
                    step=0.01,
                    key=f"help_pc_top_{ocr_project}",
                )
                pc_right = c3.number_input(
                    "Crop_Right_Ratio_PC",
                    min_value=0.0,
                    max_value=1.0,
                    value=float(
                        row_setting.get(
                            "Crop_Right_Ratio_PC",
                            AppConfig.OCR_DEFAULTS_PC["Crop_Right_Ratio_PC"],
                        )
                    ),
                    step=0.01,
                    key=f"help_pc_right_{ocr_project}",
                )
                pc_bottom = c4.number_input(
                    "Crop_Bottom_Ratio_PC",
                    min_value=0.0,
                    max_value=1.0,
                    value=float(
                        row_setting.get(
                            "Crop_Bottom_Ratio_PC",
                            AppConfig.OCR_DEFAULTS_PC["Crop_Bottom_Ratio_PC"],
                        )
                    ),
                    step=0.01,
                    key=f"help_pc_bottom_{ocr_project}",
                )

                st.markdown("##### Mobile")
                c5, c6, c7, c8 = st.columns(4)
                mobile_left = c5.number_input(
                    "Crop_Left_Ratio_Mobile",
                    min_value=0.0,
                    max_value=1.0,
                    value=float(
                        row_setting.get(
                            "Crop_Left_Ratio_Mobile",
                            AppConfig.OCR_DEFAULTS_MOBILE["Crop_Left_Ratio_Mobile"],
                        )
                    ),
                    step=0.01,
                    key=f"help_mobile_left_{ocr_project}",
                )
                mobile_top = c6.number_input(
                    "Crop_Top_Ratio_Mobile",
                    min_value=0.0,
                    max_value=1.0,
                    value=float(
                        row_setting.get(
                            "Crop_Top_Ratio_Mobile",
                            AppConfig.OCR_DEFAULTS_MOBILE["Crop_Top_Ratio_Mobile"],
                        )
                    ),
                    step=0.01,
                    key=f"help_mobile_top_{ocr_project}",
                )
                mobile_right = c7.number_input(
                    "Crop_Right_Ratio_Mobile",
                    min_value=0.0,
                    max_value=1.0,
                    value=float(
                        row_setting.get(
                            "Crop_Right_Ratio_Mobile",
                            AppConfig.OCR_DEFAULTS_MOBILE["Crop_Right_Ratio_Mobile"],
                        )
                    ),
                    step=0.01,
                    key=f"help_mobile_right_{ocr_project}",
                )
                mobile_bottom = c8.number_input(
                    "Crop_Bottom_Ratio_Mobile",
                    min_value=0.0,
                    max_value=1.0,
                    value=float(
                        row_setting.get(
                            "Crop_Bottom_Ratio_Mobile",
                            AppConfig.OCR_DEFAULTS_MOBILE["Crop_Bottom_Ratio_Mobile"],
                        )
                    ),
                    step=0.01,
                    key=f"help_mobile_bottom_{ocr_project}",
                )

                st.markdown("#### OCR確認用画像アップロード")
                preview = st.file_uploader(
                    "画像をアップロードすると赤枠プレビューします",
                    type=["png", "jpg", "jpeg"],
                    key="help_ocr_preview",
                )

                if preview is not None:
                    try:
                        file_bytes = preview.getvalue()

                        custom_mobile_box = {
                            "CUSTOM_MOBILE": {
                                "left": float(mobile_left),
                                "top": float(mobile_top),
                                "right": float(mobile_right),
                                "bottom": float(mobile_bottom),
                            }
                        }
                        custom_pc_box = {
                            "CUSTOM_PC": {
                                "left": float(pc_left),
                                "top": float(pc_top),
                                "right": float(pc_right),
                                "bottom": float(pc_bottom),
                            }
                        }

                        smartvault_boxes = AppConfig.SMARTVAULT_BOXES_MOBILE

                        st.markdown("##### 元画像")
                        st.image(file_bytes, caption="元画像", use_container_width=True)

                        st.markdown("##### SmartVault固定赤枠プレビュー")
                        smart_boxed = U.draw_ocr_boxes(file_bytes, smartvault_boxes)
                        st.image(smart_boxed, caption="SmartVault固定赤枠", use_container_width=True)

                        st.markdown("##### あなたのMobile座標 赤枠プレビュー")
                        mobile_boxed = U.draw_ocr_boxes(file_bytes, custom_mobile_box)
                        st.image(mobile_boxed, caption="現在のMobile設定", use_container_width=True)

                        st.markdown("##### あなたのPC座標 赤枠プレビュー")
                        pc_boxed = U.draw_ocr_boxes(file_bytes, custom_pc_box)
                        st.image(pc_boxed, caption="現在のPC設定", use_container_width=True)

                    except Exception as e:
                        st.error(f"赤枠プレビュー表示でエラー: {e}")

                if st.button("OCR座標を保存", key=f"help_save_ocr_{ocr_project}", use_container_width=True):
                    try:
                        idx = settings_df[settings_df["Project_Name"] == ocr_project].index[0]
                        settings_df.loc[idx, "Crop_Left_Ratio_PC"] = U.to_ratio(
                            pc_left, AppConfig.OCR_DEFAULTS_PC["Crop_Left_Ratio_PC"]
                        )
                        settings_df.loc[idx, "Crop_Top_Ratio_PC"] = U.to_ratio(
                            pc_top, AppConfig.OCR_DEFAULTS_PC["Crop_Top_Ratio_PC"]
                        )
                        settings_df.loc[idx, "Crop_Right_Ratio_PC"] = U.to_ratio(
                            pc_right, AppConfig.OCR_DEFAULTS_PC["Crop_Right_Ratio_PC"]
                        )
                        settings_df.loc[idx, "Crop_Bottom_Ratio_PC"] = U.to_ratio(
                            pc_bottom, AppConfig.OCR_DEFAULTS_PC["Crop_Bottom_Ratio_PC"]
                        )

                        settings_df.loc[idx, "Crop_Left_Ratio_Mobile"] = U.to_ratio(
                            mobile_left, AppConfig.OCR_DEFAULTS_MOBILE["Crop_Left_Ratio_Mobile"]
                        )
                        settings_df.loc[idx, "Crop_Top_Ratio_Mobile"] = U.to_ratio(
                            mobile_top, AppConfig.OCR_DEFAULTS_MOBILE["Crop_Top_Ratio_Mobile"]
                        )
                        settings_df.loc[idx, "Crop_Right_Ratio_Mobile"] = U.to_ratio(
                            mobile_right, AppConfig.OCR_DEFAULTS_MOBILE["Crop_Right_Ratio_Mobile"]
                        )
                        settings_df.loc[idx, "Crop_Bottom_Ratio_Mobile"] = U.to_ratio(
                            mobile_bottom, AppConfig.OCR_DEFAULTS_MOBILE["Crop_Bottom_Ratio_Mobile"]
                        )
                        settings_df.loc[idx, "UpdatedAt_JST"] = U.fmt_dt(U.now_jst())

                        self.repo.write_settings(settings_df)
                        self.store.persist_and_refresh()
                        st.success("OCR設定を保存しました。")
                        st.rerun()
                    except Exception as e:
                        st.error(f"OCR設定保存でエラー: {e}")

        with st.expander("15. よくある変更例", expanded=False):
            st.markdown(
                """
### 管理者を追加したい
1. Secrets の `[[admin.users]]` を追加  
2. `[line.tokens]` に同じ namespace を追加

### 新しいプロジェクトを追加したい
1. Settings に `Project_Name` を追加  
2. `Net_Factor / Compound_Timing / Active` を設定  
3. Members に対象メンバーを追加

### メンバーを追加したい
1. Members に `Project_Name / PersonName / Principal / Rank / Line_User_ID` を追加

### LINE送信先を変えたい
1. Members の `Line_User_ID` を変更

### OCRがずれる
1. このヘルプの「OCR設定」を開く  
2. 画像をアップロード  
3. 赤枠を見ながら座標を修正  
4. 保存

### 同じ画像や同じ時間の画像を上げても重複させたくない
1. `OCR_Transaction_History` シートを作成  
2. 項目名をこのヘルプから貼る  
3. APR画面の「受け取ったUSDC OCR集計（重複防止）」を使う
"""
            )

        with st.expander("16. トラブル時の確認順", expanded=False):
            st.markdown(
                """
### LINE送信できない
1. `Members.Line_User_ID` が正しいか  
2. `Secrets.line.tokens[namespace]` が正しいか  
3. 現在ログイン中の管理者 namespace が想定通りか  
4. Ledger の LINE履歴の HTTPコードを確認

### Google Sheets接続できない
1. `connections.gsheets.spreadsheet` が正しいか  
2. サービスアカウントJSONが正しいか  
3. スプレッドシートがサービスアカウントに共有されているか

### OCRが読めない
1. OCR.space APIキーが正しいか  
2. OCR座標が合っているか  
3. 画像解像度が低すぎないか

### OCR取引が重複判定されない
1. `OCR_Transaction_History` シートがあるか  
2. `Unique_Key` 列があるか  
3. OCR結果の `Date_Label / Time_Label / Type_Label / Amount_USD` が安定しているか

### Active=TRUE のプロジェクトが出ない
1. Settings の `Active` 列を確認  
2. `Project_Name` が空でないか確認
"""
            )

        with st.expander("17. Settings自動修復", expanded=False):
            st.markdown(
                """
Settings シートの不足列補完、PERSONAL行の不足補完、OCR初期座標の補完を行います。  
シート構造が崩れたときはこちらを実行してください。
"""
            )
            if st.button("Settingsを自動修復", key="help_fix_settings", use_container_width=True):
                try:
                    self.repo.repair_settings(self.repo.load_settings())
                    self.store.persist_and_refresh()
                    st.success(f"{self.repo.gs.names.SETTINGS} を修復しました。")
                    st.rerun()
                except Exception as e:
                    st.error(f"Settings修復でエラー: {e}")

        st.success("ヘルプページ読み込み完了")
