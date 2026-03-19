import streamlit as st


class APRPage:

    def __init__(self, repo, engine, store):
        self.repo = repo
        self.engine = engine
        self.store = store

    def render(self, settings_df, members_df):

        st.title("APR管理")

        st.info("APRページは現在作成中です")

        st.write("Settings")
        st.dataframe(settings_df)

        st.write("Members")
        st.dataframe(members_df)
