from __future__ import annotations

import streamlit as st


class AdminAuth:
    KEY_NAMESPACE = "admin_namespace"
    KEY_LABEL = "admin_label"
    KEY_AUTH = "admin_authenticated"

    @classmethod
    def require_login(cls) -> None:
        if st.session_state.get(cls.KEY_AUTH):
            return

        st.title("🔐 管理者ログイン")

        admins = st.secrets.get("admin", {}).get("users", [])

        if not admins:
            st.error("secrets.toml に admin.users が設定されていません")
            st.stop()

        names = [a["name"] for a in admins]
        selected = st.selectbox("管理者選択", names)

        pin = st.text_input("PIN", type="password")

        if st.button("ログイン", use_container_width=True):
            for a in admins:
                if a["name"] == selected and str(a["pin"]) == str(pin):
                    st.session_state[cls.KEY_AUTH] = True
                    st.session_state[cls.KEY_NAMESPACE] = a["namespace"]
                    st.session_state[cls.KEY_LABEL] = a["name"]
                    st.rerun()

            st.error("PINが間違っています")

        st.stop()

    @classmethod
    def current_namespace(cls) -> str:
        return st.session_state.get(cls.KEY_NAMESPACE, "A")

    @classmethod
    def current_label(cls) -> str:
        return st.session_state.get(cls.KEY_LABEL, "未ログイン")

    @classmethod
    def logout(cls) -> None:
        for k in [cls.KEY_AUTH, cls.KEY_NAMESPACE, cls.KEY_LABEL]:
            if k in st.session_state:
                del st.session_state[k]
