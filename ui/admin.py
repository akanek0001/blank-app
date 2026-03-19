    def _get_smartvault_boxes(
        self,
        settings_df: pd.DataFrame,
        project: str,
        platform: str,
    ) -> Optional[Dict[str, Dict[str, float]]]:
        srow = self._get_setting_row(settings_df, project)

        if srow is None:
            st.error(f"Settings にプロジェクト '{project}' の設定行がありません。")
            return None

        try:
            if platform == "mobile":
                required_cols = [
                    "SV_Total_Liquidity_Left",
                    "SV_Total_Liquidity_Top",
                    "SV_Total_Liquidity_Right",
                    "SV_Total_Liquidity_Bottom",
                    "SV_Yesterday_Profit_Left",
                    "SV_Yesterday_Profit_Top",
                    "SV_Yesterday_Profit_Right",
                    "SV_Yesterday_Profit_Bottom",
                    "SV_APR_Left",
                    "SV_APR_Top",
                    "SV_APR_Right",
                    "SV_APR_Bottom",
                ]

                missing = [c for c in required_cols if c not in srow.index]
                if missing:
                    st.error(f"Settings に mobile 用 SmartVault 座標列がありません: {', '.join(missing)}")
                    return None

                values = {c: str(srow.get(c, "")).strip() for c in required_cols}
                empty = [k for k, v in values.items() if v == ""]
                if empty:
                    st.error(f"Settings の mobile 用 SmartVault 座標が未入力です: {', '.join(empty)}")
                    return None

                return {
                    "TOTAL_LIQUIDITY": {
                        "left": float(values["SV_Total_Liquidity_Left"]),
                        "top": float(values["SV_Total_Liquidity_Top"]),
                        "right": float(values["SV_Total_Liquidity_Right"]),
                        "bottom": float(values["SV_Total_Liquidity_Bottom"]),
                    },
                    "YESTERDAY_PROFIT": {
                        "left": float(values["SV_Yesterday_Profit_Left"]),
                        "top": float(values["SV_Yesterday_Profit_Top"]),
                        "right": float(values["SV_Yesterday_Profit_Right"]),
                        "bottom": float(values["SV_Yesterday_Profit_Bottom"]),
                    },
                    "APR": {
                        "left": float(values["SV_APR_Left"]),
                        "top": float(values["SV_APR_Top"]),
                        "right": float(values["SV_APR_Right"]),
                        "bottom": float(values["SV_APR_Bottom"]),
                    },
                }

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
                st.error(f"Settings に PC 用 SmartVault 座標列がありません: {', '.join(missing)}")
                return None

            values = {c: str(srow.get(c, "")).strip() for c in required_cols}
            empty = [k for k, v in values.items() if v == ""]
            if empty:
                st.error(f"Settings の PC 用 SmartVault 座標が未入力です: {', '.join(empty)}")
                return None

            return {
                "TOTAL_LIQUIDITY": {
                    "left": float(values["SV_Total_Liquidity_Left_PC"]),
                    "top": float(values["SV_Total_Liquidity_Top_PC"]),
                    "right": float(values["SV_Total_Liquidity_Right_PC"]),
                    "bottom": float(values["SV_Total_Liquidity_Bottom_PC"]),
                },
                "YESTERDAY_PROFIT": {
                    "left": float(values["SV_Yesterday_Profit_Left_PC"]),
                    "top": float(values["SV_Yesterday_Profit_Top_PC"]),
                    "right": float(values["SV_Yesterday_Profit_Right_PC"]),
                    "bottom": float(values["SV_Yesterday_Profit_Bottom_PC"]),
                },
                "APR": {
                    "left": float(values["SV_APR_Left_PC"]),
                    "top": float(values["SV_APR_Top_PC"]),
                    "right": float(values["SV_APR_Right_PC"]),
                    "bottom": float(values["SV_APR_Bottom_PC"]),
                },
            }

        except Exception as e:
            st.error(f"SmartVault 座標の読込でエラー: {e}")
            return None
