この ZIP は blank-app-main をベースに、次を修正した GitHub アップロード用セットです。

- controller/app_controller.py
  - サイドバー構成を Dashboard / APR / Cash / 管理 / ヘルプ に維持
  - 既存 ui.* ページ構成に統一

- core/utils.py
  - to_num_series を混在型に強い実装へ修正

- ui/dashboard.py
  - st.dataframe 依存をやめ、HTML テーブル表示へ変更

- ui/apr.py
  - 個人別本日配当の表示を HTML テーブルへ変更
  - SmartVault OCR プレビューを width=500 に変更

- ui/help.py
  - SmartVault 固定赤枠表示を削除
  - Mobile / PC の座標プレビューのみ残す

使い方
1. ZIP を解凍
2. 中身を GitHub リポジトリへそのまま上書き
3. Streamlit Cloud を再デプロイ
