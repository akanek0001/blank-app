from __future__ import annotations

import streamlit as st


class AdminAuth:
    KEY_NAMESPACE = "admin_namespace"
    KEY_LABEL = "admin_label"
    KEY_AUTH = "admin_authenticated"

    @classmethod
    def _load_admins(cls) -> list[dict]:
        try:
            admins = st.secrets["admin"]["users"]
            return list(admins)
        except Exception:
            return []

    @classmethod
    def require_login(cls) -> None:
        if st.session_state.get(cls.KEY_AUTH):
            return

        st.title("🔐 管理者ログイン")

        admins = cls._load_admins()

        if not admins:
            st.error("secrets.toml に admin.users が設定されていません")
            st.write("DEBUG st.secrets keys:", list(st.secrets.keys()))
            if "admin" in st.secrets:
                st.write("DEBUG st.secrets['admin']:", st.secrets["admin"])
            st.stop()

        names = [str(a["name"]) for a in admins]
        selected = st.selectbox("管理者選択", names)
        pin = st.text_input("PIN", type="password")

        if st.button("ログイン", use_container_width=True):
            for a in admins:
                if str(a["name"]) == str(selected) and str(a["pin"]) == str(pin):
                    st.session_state[cls.KEY_AUTH] = True
                    st.session_state[cls.KEY_NAMESPACE] = str(a["namespace"])
                    st.session_state[cls.KEY_LABEL] = str(a["name"])
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


# END OF FILE
