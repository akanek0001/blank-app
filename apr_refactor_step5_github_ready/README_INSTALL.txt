GitHub配置手順

1. services/ocr_processor.py を追加
2. services/transaction_manager.py を追加
3. pages/apr_page.py を追加
4. controller/app_controller.py を上書き

配置先:

blank-app/
├─ controller/
│  └─ app_controller.py
├─ pages/
│  └─ apr_page.py
├─ services/
│  ├─ ocr_processor.py
│  └─ transaction_manager.py

注意:
- この工程は「接続まで」です。
- 既存 ui/apr.py は残して問題ありません。
- 次工程で pages/apr_page.py を既存機能へ寄せていきます。
