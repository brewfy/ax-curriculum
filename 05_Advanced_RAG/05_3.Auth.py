"""
인증 및 보안 관련 유틸리티
"""
import os
import hashlib
import time
import streamlit as st
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# ── Mock 데이터 및 상수 ──────────────────────────────────────
# 비밀번호 'admin'의 SHA-256 해시값
ADMIN_HASH = "8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918"
TOKEN_KEY  = "access_token"
_CLIENT_KEY = "_openai_client"

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def create_mock_token(username: str) -> str:
    # 간단한 Mock 토큰 생성 (Base64 등 대신 세션 식별용)
    return f"mock_atk_{username}_{int(time.time())}"

def verify_login(username, password) -> bool:
    if username == "admin" and hash_password(password) == ADMIN_HASH:
        token = create_mock_token(username)
        st.session_state[TOKEN_KEY] = token
        return True
    return False

def is_logged_in() -> bool:
    return TOKEN_KEY in st.session_state

def logout():
    if TOKEN_KEY in st.session_state:
        del st.session_state[TOKEN_KEY]
    st.rerun()

# ── OpenAI 인증 관련 ──────────────────────────────────────────
def get_api_key() -> str:
    return (
        st.session_state.get("api_key_input", "")
        or os.getenv("OPENAI_API_KEY", "")
    )

def get_openai_client() -> OpenAI:
    api_key = get_api_key()
    if not api_key: return None

    cached = st.session_state.get(_CLIENT_KEY)
    if cached and getattr(cached, "_api_key", None) == api_key:
        return cached

    client = OpenAI(api_key=api_key)
    client._api_key = api_key
    st.session_state[_CLIENT_KEY] = client
    return client

# ── UI 컴포넌트 ───────────────────────────────────────────────
def login_page():
    """로그인 페이지 렌더링"""
    st.markdown("""
        <style>
        /* [data-testid="stVerticalBlock"] > div:has(.login-box) { display: flex; justify-content: center; } */
        .login-box {
            padding: 2.5rem;
            background: #ffffff;
            border-radius: 16px;
            box-shadow: 0 15px 35px rgba(0,0,0,0.08);
            border: 1px solid #eaeaea;
            margin-top: 20vh;
        }
        .login-header {
            text-align: center;
            font-weight: 800;
            color: #111;
            margin-bottom: 2rem;
            font-size: 1.6rem;
            letter-spacing: -0.02em;
        }
        </style>
    """, unsafe_allow_html=True)
    
    # 컬럼을 사용하여 중앙 배치
    col_left, col_mid, col_right = st.columns([1, 1.2, 1])
    
    with col_mid:
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
        
        # st.markdown('<p style="font-size:0.75rem; color:#aaa; text-align:center; margin-top:1.5rem;">admin / admin 으로 로그인하세요</p>', unsafe_allow_html=True)

def render_api_key_status() -> bool:
    """사이드바에 API 키 상태 표시"""
    env_key = os.getenv("OPENAI_API_KEY", "")
    if env_key:
        st.sidebar.markdown(
            '<div style="color:#1a7a4a; font-size:0.78rem; padding:0.2rem 0;">✓ 시스템 API 키 로드됨</div>',
            unsafe_allow_html=True,
        )
        return True
    
    # 환경변수 없으면 수동 입력 유도
    st.sidebar.markdown('<div class="section-header">API Key</div>', unsafe_allow_html=True)
    key = st.sidebar.text_input("OpenAI Key", type="password", key="api_key_input")
    return bool(key)
