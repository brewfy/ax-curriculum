"""
인증 유틸리티 (Streamlit Cloud 전용 — 세션 기반)
"""
import hashlib
import time
import streamlit as st

ADMIN_HASH = "8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918"
TOKEN_KEY  = "access_token"


def _hash(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()


def verify_login(username: str, password: str) -> bool:
    if username == "admin" and _hash(password) == ADMIN_HASH:
        st.session_state[TOKEN_KEY] = f"tok_{username}_{int(time.time())}"
        return True
    return False


def is_logged_in() -> bool:
    return TOKEN_KEY in st.session_state


def logout():
    st.session_state.pop(TOKEN_KEY, None)
    st.rerun()


def login_page():
    st.markdown("""
    <style>
    .login-header { text-align:center; font-weight:800; color:#111; margin-bottom:2rem; font-size:1.6rem; letter-spacing:-0.02em; }
    </style>
    """, unsafe_allow_html=True)
    _, col, _ = st.columns([1, 1.2, 1])
    with col:
        st.markdown('<div class="login-header">커리큘럼 생성</div>', unsafe_allow_html=True)
        user = st.text_input("Username", placeholder="admin", label_visibility="collapsed")
        st.markdown('<div style="height:0.5rem"></div>', unsafe_allow_html=True)
        pw   = st.text_input("Password", type="password", placeholder="password", label_visibility="collapsed")
        st.markdown('<div style="height:1.5rem"></div>', unsafe_allow_html=True)
        if st.button("Sign In", use_container_width=True, type="primary"):
            if verify_login(user, pw):
                st.success("로그인 성공!")
                time.sleep(0.5)
                st.rerun()
            else:
                st.error("Invalid credentials")
