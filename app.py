import os
import time
import sqlite3
from datetime import datetime

import pandas as pd
import requests
import streamlit as st


# =====================================================
# CONFIG
# =====================================================

st.set_page_config(
    page_title="SAP CostShield AI",
    page_icon="🛡️",
    layout="wide"
)

DB_NAME = "costshield.db"


# =====================================================
# SECRETS
# =====================================================

def secret(name, default=""):
    try:
        return st.secrets[name]
    except:
        return os.getenv(name, default)


OPENWEATHER_API_KEY = secret("OPENWEATHER_API_KEY")
GOOGLE_ROUTES_API_KEY = secret("GOOGLE_ROUTES_API_KEY")

REFRESH_SECONDS = int(
    secret("REFRESH_SECONDS", 60)
)


# =====================================================
# DATABASE
# =====================================================

def connect():

    return sqlite3.connect(
        DB_NAME,
        check_same_thread=False
    )


def init_db():

    conn = connect()

    conn.execute("""
    CREATE TABLE IF NOT EXISTS risks(
        id INTEGER PRIMARY KEY,
        timestamp TEXT,
        score REAL,
        status TEXT
    )
    """)

    conn.execute("""
    CREATE TABLE IF NOT EXISTS alerts(
        id INTEGER PRIMARY KEY,
        timestamp TEXT,
        severity TEXT,
        message TEXT
    )
    """)

    conn.execute("""
    CREATE TABLE IF NOT EXISTS suppliers(
        id INTEGER PRIMARY KEY,
        name TEXT,
        reliability REAL,
        capacity REAL
    )
    """)

    conn.commit()
    conn.close()


init_db()


# =====================================================
# WEATHER
# =====================================================

def weather_risk(city):

    if not OPENWEATHER_API_KEY:
        return 0

    try:

        r = requests.get(
            "https://api.openweathermap.org/data/2.5/weather",
            params={
                "q": city,
                "appid": OPENWEATHER_API_KEY,
                "units": "metric"
            }
        )

        data = r.json()

        weather_id = (
            data["weather"][0]["id"]
        )

        if 200 <= weather_id < 300:
            return 90

        if 300 <= weather_id < 600:
            return 60

        if 600 <= weather_id < 700:
            return 75

        return 20

    except:
        return 0


# =====================================================
# RISK ENGINE
# =====================================================

def calculate_risk(

    weather,
    traffic,
    factory,
    port

):

    score = (

        weather * 0.25 +

        traffic * 0.25 +

        factory * 0.25 +

        port * 0.25

    )

    score = round(score, 1)

    if score >= 70:
        status = "CRITICAL"

    elif score >= 45:
        status = "ELEVATED"

    else:
        status = "STABLE"

    return score, status


# =====================================================
# SAVE RISK
# =====================================================

def save_risk(score, status):

    conn = connect()

    conn.execute(
        """
        INSERT INTO risks
        (
            timestamp,
            score,
            status
        )
        VALUES
        (?, ?, ?)
        """,
        (
            datetime.now().isoformat(),
            score,
            status
        )
    )

    conn.commit()
    conn.close()


# =====================================================
# ALERTS
# =====================================================

def create_alert(severity, message):

    conn = connect()

    conn.execute(
        """
        INSERT INTO alerts
        (
            timestamp,
            severity,
            message
        )
        VALUES
        (?, ?, ?)
        """,
        (
            datetime.now().isoformat(),
            severity,
            message
        )
    )

    conn.commit()
    conn.close()


# =====================================================
# SIDEBAR
# =====================================================

st.sidebar.title("🛡️ SAP CostShield AI")

page = st.sidebar.radio(
    "Navigation",
    [
        "Dashboard",
        "Live Monitoring",
        "Risk Prediction",
        "Suppliers",
        "Alerts",
        "System Health"
    ]
)

auto_refresh = st.sidebar.checkbox(
    "Auto Refresh"
)


# =====================================================
# DASHBOARD
# =====================================================

if page == "Dashboard":

    st.title("Executive Dashboard")

    conn = connect()

    risks = pd.read_sql(
        "SELECT * FROM risks",
        conn
    )

    alerts = pd.read_sql(
        "SELECT * FROM alerts",
        conn
    )

    suppliers = pd.read_sql(
        "SELECT * FROM suppliers",
        conn
    )

    conn.close()

    c1, c2, c3 = st.columns(3)

    c1.metric(
        "Risk Records",
        len(risks)
    )

    c2.metric(
        "Alerts",
        len(alerts)
    )

    c3.metric(
        "Suppliers",
        len(suppliers)
    )

    if not risks.empty:

        st.line_chart(
            risks["score"]
        )


# =====================================================
# LIVE MONITORING
# =====================================================

elif page == "Live Monitoring":

    st.title("Live Monitoring")

    city = st.text_input(
        "Weather Location",
        "Mumbai"
    )

    weather = weather_risk(city)

    traffic = st.slider(
        "Traffic Risk",
        0, 100, 20
    )

    factory = st.slider(
        "Factory Risk",
        0, 100, 10
    )

    port = st.slider(
        "Port Risk",
        0, 100, 25
    )

    score, status = calculate_risk(
        weather,
        traffic,
        factory,
        port
    )

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Risk Score",
        score
    )

    col2.metric(
        "Status",
        status
    )

    col3.metric(
        "Weather Risk",
        weather
    )

    if st.button("Save Assessment"):

        save_risk(
            score,
            status
        )

        if status == "CRITICAL":

            create_alert(
                "CRITICAL",
                "Supply Chain Critical Risk"
            )

        st.success(
            "Assessment Saved"
        )


# =====================================================
# AI RISK PREDICTION
# =====================================================

elif page == "Risk Prediction":

    st.title(
        "AI Risk Prediction"
    )

    weather = st.slider(
        "Weather",
        0, 100, 25
    )

    traffic = st.slider(
        "Traffic",
        0, 100, 20
    )

    factory = st.slider(
        "Factory",
        0, 100, 10
    )

    port = st.slider(
        "Port",
        0, 100, 30
    )

    score, status = calculate_risk(
        weather,
        traffic,
        factory,
        port
    )

    st.metric(
        "Predicted Risk",
        score
    )

    st.metric(
        "Status",
        status
    )


# =====================================================
# SUPPLIERS
# =====================================================

elif page == "Suppliers":

    st.title(
        "Supplier Intelligence"
    )

    with st.form("supplier"):

        name = st.text_input(
            "Supplier"
        )

        reliability = st.slider(
            "Reliability",
            0,
            100,
            90
        )

        capacity = st.slider(
            "Capacity",
            0,
            100,
            90
        )

        save = st.form_submit_button(
            "Save"
        )

    if save:

        conn = connect()

        conn.execute(
            """
            INSERT INTO suppliers
            (
                name,
                reliability,
                capacity
            )
            VALUES
            (?, ?, ?)
            """,
            (
                name,
                reliability,
                capacity
            )
        )

        conn.commit()
        conn.close()

        st.success(
            "Supplier Saved"
        )

    conn = connect()

    df = pd.read_sql(
        "SELECT * FROM suppliers",
        conn
    )

    conn.close()

    st.dataframe(df)


# =====================================================
# ALERTS
# =====================================================

elif page == "Alerts":

    st.title("Alerts")

    conn = connect()

    df = pd.read_sql(
        "SELECT * FROM alerts ORDER BY id DESC",
        conn
    )

    conn.close()

    st.dataframe(df)


# =====================================================
# SYSTEM HEALTH
# =====================================================

elif page == "System Health":

    st.title(
        "System Health"
    )

    st.success(
        "Database Connected"
    )

    st.info(
        f"Refresh Interval: "
        f"{REFRESH_SECONDS} sec"
    )

    st.write(
        "Weather API:",
        "✅ Configured"
        if OPENWEATHER_API_KEY
        else "❌ Missing"
    )

    st.write(
        "Google API:",
        "✅ Configured"
        if GOOGLE_ROUTES_API_KEY
        else "❌ Missing"
    )


# =====================================================
# AUTO REFRESH
# =====================================================

if auto_refresh:

    time.sleep(
        REFRESH_SECONDS
    )

    st.rerun()
