    @classmethod
    def get_smartvault_boxes(
        cls,
        settings_df: pd.DataFrame,
        project: str,
        platform: str,
    ) -> Dict[str, OCRBox]:
        srow = cls.get_setting_row(settings_df, project)

        if platform == "mobile":
            # Settings に SmartVault 専用列が無くても、
            # config.py の固定座標を使って必ず動くようにする
            boxes = AppConfig.SMARTVAULT_BOXES_MOBILE

            return {
                "TOTAL_LIQUIDITY": OCRBox(
                    left=float(boxes["TOTAL_LIQUIDITY"]["left"]),
                    top=float(boxes["TOTAL_LIQUIDITY"]["top"]),
                    right=float(boxes["TOTAL_LIQUIDITY"]["right"]),
                    bottom=float(boxes["TOTAL_LIQUIDITY"]["bottom"]),
                ),
                "YESTERDAY_PROFIT": OCRBox(
                    left=float(boxes["YESTERDAY_PROFIT"]["left"]),
                    top=float(boxes["YESTERDAY_PROFIT"]["top"]),
                    right=float(boxes["YESTERDAY_PROFIT"]["right"]),
                    bottom=float(boxes["YESTERDAY_PROFIT"]["bottom"]),
                ),
                "APR": OCRBox(
                    left=float(boxes["APR"]["left"]),
                    top=float(boxes["APR"]["top"]),
                    right=float(boxes["APR"]["right"]),
                    bottom=float(boxes["APR"]["bottom"]),
                ),
            }

        if srow is None:
            raise ValueError(f"Settings にプロジェクト '{project}' の設定行がありません。")

        required_cols = [
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
        ]

        missing = [c for c in required_cols if c not in srow.index]
        if missing:
            raise ValueError(
                f"Settings に PC 用 SmartVault 座標列がありません: {', '.join(missing)}"
            )

        values = {c: str(srow.get(c, "")).strip() for c in required_cols}
        empty = [k for k, v in values.items() if v == ""]
        if empty:
            raise ValueError(
                f"Settings の PC 用 SmartVault 座標が未入力です: {', '.join(empty)}"
            )

        return {
            "TOTAL_LIQUIDITY": OCRBox(
                left=float(values["SV_Total_Liquidity_Left_PC"]),
                top=float(values["SV_Total_Liquidity_Top_PC"]),
                right=float(values["SV_Total_Liquidity_Right_PC"]),
                bottom=float(values["SV_Total_Liquidity_Bottom_PC"]),
            ),
            "YESTERDAY_PROFIT": OCRBox(
                left=float(values["SV_Yesterday_Profit_Left_PC"]),
                top=float(values["SV_Yesterday_Profit_Top_PC"]),
                right=float(values["SV_Yesterday_Profit_Right_PC"]),
                bottom=float(values["SV_Yesterday_Profit_Bottom_PC"]),
            ),
            "APR": OCRBox(
                left=float(values["SV_APR_Left_PC"]),
                top=float(values["SV_APR_Top_PC"]),
                right=float(values["SV_APR_Right_PC"]),
                bottom=float(values["SV_APR_Bottom_PC"]),
            ),
        }
