```python
import os
import time
import sqlite3
from datetime import datetime, timezone

import pandas as pd
import requests
import streamlit as st


# ============================================================
# SAP COSTSHIELD AI
# ENTERPRISE SUPPLY CHAIN CONTROL TOWER
# ============================================================

st.set_page_config(
    page_title="SAP CostShield AI | Supply Chain Control Tower",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)


# ============================================================
# CONFIGURATION
# ============================================================

DB_NAME = "costshield.db"


def get_secret(name, default=""):
    try:
        if name in st.secrets:
            return st.secrets[name]
    except Exception:
        pass

    return os.getenv(name, default)


# Weather
OPENWEATHER_API_KEY = get_secret(
    "OPENWEATHER_API_KEY"
)

# Google Routes / Traffic
GOOGLE_ROUTES_API_KEY = get_secret(
    "GOOGLE_ROUTES_API_KEY"
)

# SAP S/4HANA
SAP_BASE_URL = get_secret(
    "SAP_BASE_URL"
)

SAP_USERNAME = get_secret(
    "SAP_USERNAME"
)

SAP_PASSWORD = get_secret(
    "SAP_PASSWORD"
)

SAP_TOKEN = get_secret(
    "SAP_TOKEN"
)

SAP_PO_ENDPOINT = get_secret(
    "SAP_PO_ENDPOINT",
    "/sap/opu/odata/sap/API_PURCHASEORDER_2_SRV/A_PurchaseOrder"
)

# Supplier / MES
SUPPLIER_API_URL = get_secret(
    "SUPPLIER_API_URL"
)

SUPPLIER_API_TOKEN = get_secret(
    "SUPPLIER_API_TOKEN"
)

# Port / AIS
PORT_API_URL = get_secret(
    "PORT_API_URL"
)

PORT_API_TOKEN = get_secret(
    "PORT_API_TOKEN"
)

try:
    DEFAULT_REFRESH = int(
        get_secret(
            "REFRESH_SECONDS",
            "60"
        )
    )
except Exception:
    DEFAULT_REFRESH = 60


# ============================================================
# PROFESSIONAL UI
# ============================================================

st.markdown(
    """
    <style>

    .stApp {
        background:
            radial-gradient(
                circle at top right,
                #102a43 0%,
                #07111f 42%,
                #030912 100%
            );

        color: #eaf4ff;
    }

    section[data-testid="stSidebar"] {
        background: #06101d;
        border-right: 1px solid #18344d;
    }

    div[data-testid="stMetric"] {
        background:
            linear-gradient(
                145deg,
                #10243a,
                #0b1b2d
            );

        padding: 16px;

        border-radius: 14px;

        border: 1px solid #23435f;
    }

    div[data-testid="stMetricValue"] {
        color: #8dd6ff;
    }

    h1, h2, h3 {
        color: #8dd6ff;
    }

    .hero {
        padding: 24px;

        border-radius: 18px;

        background:
            linear-gradient(
                100deg,
                rgba(10,110,209,.25),
                rgba(0,212,255,.06)
            );

        border: 1px solid #1c4d70;

        margin-bottom: 20px;
    }

    .status-box {
        padding: 12px 16px;

        border-radius: 10px;

        background: #091a2a;

        border: 1px solid #24445e;

        margin-bottom: 10px;
    }

    .muted {
        color: #91a8ba;
        font-size: 13px;
    }

    </style>
    """,
    unsafe_allow_html=True
)


# ============================================================
# DATABASE
# ============================================================

def db_connection():
    return sqlite3.connect(
        DB_NAME,
        check_same_thread=False
    )


def init_database():

    with db_connection() as conn:

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS risk_records (

                id INTEGER PRIMARY KEY AUTOINCREMENT,

                timestamp TEXT,

                traffic REAL,
                weather REAL,
                factory REAL,
                port REAL,
                geopolitical REAL,
                route REAL,
                inventory REAL,

                risk_score REAL,
                status TEXT,
                delay REAL
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS suppliers (

                id INTEGER PRIMARY KEY AUTOINCREMENT,

                name TEXT,
                location TEXT,

                reliability REAL,
                lead_time REAL,
                cost REAL,

                capacity_pct REAL
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS integration_events (

                id INTEGER PRIMARY KEY AUTOINCREMENT,

                timestamp TEXT,

                source TEXT,
                metric TEXT,

                value REAL,

                status TEXT,
                message TEXT
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS alerts (

                id INTEGER PRIMARY KEY AUTOINCREMENT,

                timestamp TEXT,

                severity TEXT,

                source TEXT,

                message TEXT,

                acknowledged INTEGER DEFAULT 0
            )
            """
        )

        conn.commit()


init_database()


# ============================================================
# LOGGING
# ============================================================

def log_event(
    source,
    metric,
    value,
    status,
    message=""
):

    with db_connection() as conn:

        conn.execute(
            """
            INSERT INTO integration_events
            (
                timestamp,
                source,
                metric,
                value,
                status,
                message
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now(
                    timezone.utc
                ).isoformat(),

                source,
                metric,
                float(value or 0),

                status,
                message
            )
        )

        conn.commit()


def create_alert(
    severity,
    source,
    message
):

    with db_connection() as conn:

        conn.execute(
            """
            INSERT INTO alerts
            (
                timestamp,
                severity,
                source,
                message
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                datetime.now(
                    timezone.utc
                ).isoformat(),

                severity,
                source,
                message
            )
        )

        conn.commit()


# ============================================================
# WEATHER API
# ============================================================

@st.cache_data(ttl=300)
def get_weather(city):

    if not OPENWEATHER_API_KEY:

        return {
            "connected": False,
            "message":
                "OPENWEATHER_API_KEY is not configured."
        }

    try:

        response = requests.get(

            "https://api.openweathermap.org/data/2.5/weather",

            params={
                "q": city,
                "appid": OPENWEATHER_API_KEY,
                "units": "metric"
            },

            timeout=20
        )

        response.raise_for_status()

        data = response.json()

        weather_data = data.get(
            "weather",
            [{}]
        )[0]

        result = {

            "connected": True,

            "city":
                data.get(
                    "name",
                    city
                ),

            "temperature":
                data.get(
                    "main",
                    {}
                ).get(
                    "temp",
                    0
                ),

            "humidity":
                data.get(
                    "main",
                    {}
                ).get(
                    "humidity",
                    0
                ),

            "wind":
                data.get(
                    "wind",
                    {}
                ).get(
                    "speed",
                    0
                ),

            "condition":
                weather_data.get(
                    "description",
                    "Unknown"
                ),

            "weather_id":
                int(
                    weather_data.get(
                        "id",
                        0
                    )
                )
        }

        risk = weather_to_risk(
            result
        )

        log_event(
            "OpenWeather",
            "weather_risk",
            risk,
            "CONNECTED",
            result["condition"]
        )

        return result

    except Exception as error:

        log_event(
            "OpenWeather",
            "weather",
            0,
            "ERROR",
            str(error)
        )

        return {
            "connected": False,
            "message": str(error)
        }


def weather_to_risk(
    weather
):

    if not weather.get(
        "connected"
    ):
        return 0

    weather_id = weather.get(
        "weather_id",
        0
    )

    if 200 <= weather_id < 300:
        return 90

    if 300 <= weather_id < 600:
        return 65

    if 600 <= weather_id < 700:
        return 75

    if 700 <= weather_id < 800:
        return 50

    if weather_id == 800:
        return 10

    if 801 <= weather_id <= 804:
        return 20

    return 30


# ============================================================
# GOOGLE ROUTES / TRAFFIC
# ============================================================

def calculate_route(
    origin,
    destination
):

    if not GOOGLE_ROUTES_API_KEY:

        raise ValueError(
            "GOOGLE_ROUTES_API_KEY "
            "is not configured."
        )

    response = requests.post(

        "https://routes.googleapis.com/"
        "directions/v2:computeRoutes",

        headers={

            "Content-Type":
                "application/json",

            "X-Goog-Api-Key":
                GOOGLE_ROUTES_API_KEY,

            "X-Goog-FieldMask":
                "routes.duration,"
                "routes.distanceMeters,"
                "routes.staticDuration"
        },

        json={

            "origin": {
                "address": origin
            },

            "destination": {
                "address": destination
            },

            "travelMode":
                "DRIVE",

            "routingPreference":
                "TRAFFIC_AWARE"
        },

        timeout=30
    )

    response.raise_for_status()

    routes = response.json().get(
        "routes",
        []
    )

    if not routes:

        raise ValueError(
            "Google Routes returned no route."
        )

    return routes[0]


def duration_seconds(
    value
):

    if not value:
        return 0

    try:

        return float(
            str(value).replace(
                "s",
                ""
            )
        )

    except Exception:

        return 0


def traffic_risk(
    route
):

    live = duration_seconds(
        route.get("duration")
    )

    normal = duration_seconds(
        route.get("staticDuration")
    )

    if normal <= 0:
        return 0

    extra_percent = max(
        0,
        (live / normal - 1) * 100
    )

    return round(
        min(
            100,
            extra_percent * 2
        ),
        2
    )


# ============================================================
# SAP S/4HANA
# ============================================================

def sap_configured():

    return bool(
        SAP_BASE_URL
        and (
            SAP_TOKEN
            or (
                SAP_USERNAME
                and SAP_PASSWORD
            )
        )
    )


def sap_headers():

    headers = {
        "Accept":
            "application/json",
        "Content-Type":
            "application/json"
    }

    if SAP_TOKEN:

        headers["Authorization"] = (
            f"Bearer {SAP_TOKEN}"
        )

    return headers


def get_sap_purchase_orders():

    if not sap_configured():

        return (
            pd.DataFrame(),
            "SAP S/4HANA is not configured."
        )

    url = (
        SAP_BASE_URL.rstrip("/")
        + "/"
        + SAP_PO_ENDPOINT.lstrip("/")
    )

    try:

        auth = None

        if (
            SAP_USERNAME
            and SAP_PASSWORD
            and not SAP_TOKEN
        ):

            auth = (
                SAP_USERNAME,
                SAP_PASSWORD
            )

        response = requests.get(

            url,

            headers=sap_headers(),

            auth=auth,

            params={
                "$format": "json",
                "$top": 100
            },

            timeout=30
        )

        response.raise_for_status()

        payload = response.json()

        rows = (
            payload
            .get("d", {})
            .get("results", [])
        )

        if not rows:

            rows = payload.get(
                "value",
                []
            )

        records = []

        for row in rows:

            records.append({

                "PO Number":
                    row.get(
                        "PurchaseOrder",
                        row.get(
                            "PO_Number",
                            ""
                        )
                    ),

                "Supplier":
                    row.get(
                        "SupplierName",
                        row.get(
                            "Supplier",
                            ""
                        )
                    ),

                "Origin":
                    row.get(
                        "Origin",
                        ""
                    ),

                "Destination":
                    row.get(
                        "Destination",
                        ""
                    ),

                "Order Value":
                    float(
                        row.get(
                            "TotalNetAmount",
                            row.get(
                                "Order_Value_USD",
                                0
                            )
                        )
                        or 0
                    ),

                "Lead Time":
                    float(
                        row.get(
                            "PlannedLeadTime",
                            0
                        )
                        or 0
                    ),

                "Status":
                    row.get(
                        "Status",
                        "OPEN"
                    )
            })

        result = pd.DataFrame(
            records
        )

        log_event(
            "SAP S/4HANA",
            "purchase_orders",
            len(result),
            "CONNECTED",
            "SAP purchase orders received."
        )

        return (
            result,
            "SAP purchase orders received."
        )

    except Exception as error:

        log_event(
            "SAP S/4HANA",
            "purchase_orders",
            0,
            "ERROR",
            str(error)
        )

        return (
            pd.DataFrame(),
            str(error)
        )


# ============================================================
# SUPPLIER / MES API
# ============================================================

def get_supplier_capacity():

    if not SUPPLIER_API_URL:

        return (
            pd.DataFrame(),
            "SUPPLIER_API_URL is not configured."
        )

    headers = {
        "Accept":
            "application/json"
    }

    if SUPPLIER_API_TOKEN:

        headers["Authorization"] = (
            f"Bearer {SUPPLIER_API_TOKEN}"
        )

    try:

        response = requests.get(

            SUPPLIER_API_URL,

            headers=headers,

            timeout=30
        )

        response.raise_for_status()

        payload = response.json()

        if isinstance(
            payload,
            dict
        ):

            rows = payload.get(
                "suppliers",
                []
            )

        else:

            rows = payload

        records = []

        for row in rows:

            records.append({

                "Supplier":
                    row.get(
                        "supplier",
                        row.get(
                            "name",
                            ""
                        )
                    ),

                "Capacity (%)":
                    float(
                        row.get(
                            "capacity_pct",
                            row.get(
                                "capacity",
                                0
                            )
                        )
                        or 0
                    ),

                "Production Status":
                    row.get(
                        "production_status",
                        "UNKNOWN"
                    ),

                "Updated":
                    row.get(
                        "updated_at",
                        ""
                    )
            })

        result = pd.DataFrame(
            records
        )

        log_event(
            "Supplier/MES",
            "factory_capacity",
            len(result),
            "CONNECTED",
            "Supplier capacity received."
        )

        return (
            result,
            "Supplier/MES data received."
        )

    except Exception as error:

        log_event(
            "Supplier/MES",
            "factory_capacity",
            0,
            "ERROR",
            str(error)
        )

        return (
            pd.DataFrame(),
            str(error)
        )


# ============================================================
# PORT / AIS API
# ============================================================

def get_port_status():

    if not PORT_API_URL:

        return (
            pd.DataFrame(),
            "PORT_API_URL is not configured."
        )

    headers = {
        "Accept":
            "application/json"
    }

    if PORT_API_TOKEN:

        headers["Authorization"] = (
            f"Bearer {PORT_API_TOKEN}"
        )

    try:

        response = requests.get(

            PORT_API_URL,

            headers=headers,

            timeout=30
        )

        response.raise_for_status()

        payload = response.json()

        if isinstance(
            payload,
            dict
        ):

            rows = payload.get(
                "ports",
                []
            )

        else:

            rows = payload

        records = []

        for row in rows:

            records.append({

                "Port":
                    row.get(
                        "port",
                        row.get(
                            "name",
                            ""
                        )
                    ),

                "Congestion":
                    float(
                        row.get(
                            "congestion_index",
                            row.get(
                                "congestion",
                                0
                            )
                        )
                        or 0
                    ),

                "Vessels Waiting":
                    float(
                        row.get(
                            "vessels_waiting",
                            0
                        )
                        or 0
                    ),

                "Status":
                    row.get(
                        "status",
                        "UNKNOWN"
                    ),

                "Updated":
                    row.get(
                        "updated_at",
                        ""
                    )
            })

        result = pd.DataFrame(
            records
        )

        log_event(
            "Port/AIS",
            "port_status",
            len(result),
            "CONNECTED",
            "Port telemetry received."
        )

        return (
            result,
            "Port/AIS data received."
        )

    except Exception as error:

        log_event(
            "Port/AIS",
            "port_status",
            0,
            "ERROR",
            str(error)
        )

        return (
            pd.DataFrame(),
            str(error)
        )


# ============================================================
# AI RISK ENGINE
# ============================================================

def calculate_risk(data):

    score = (

        data["traffic"] * 0.24

        + data["weather"] * 0.20

        + (
            100 - data["factory"]
        ) * 0.20

        + data["port"] * 0.14

        + data["geopolitical"] * 0.10

        + data["route"] * 0.08

        + max(
            0,
            7 - data["inventory"]
        ) * 0.04
    )

    score = max(
        0,
        min(
            100,
            score
        )
    )

    if score >= 70:

        status = "CRITICAL"

    elif score >= 45:

        status = "ELEVATED"

    else:

        status = "STABLE"

    delay = max(
        0,
        (score - 35) / 12
    )

    return {

        "risk_score":
            round(
                score,
                2
            ),

        "status":
            status,

        "delay":
            round(
                delay,
                2
            )
    }


def save_risk(
    data,
    result
):

    with db_connection() as conn:

        conn.execute(
            """
            INSERT INTO risk_records
            (
                timestamp,
                traffic,
                weather,
                factory,
                port,
                geopolitical,
                route,
                inventory,
                risk_score,
                status,
                delay
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now(
                    timezone.utc
                ).isoformat(),

                data["traffic"],
                data["weather"],
                data["factory"],
                data["port"],
                data["geopolitical"],
                data["route"],
                data["inventory"],

                result["risk_score"],
                result["status"],
                result["delay"]
            )
        )

        conn.commit()


def get_risks():

    with db_connection() as conn:

        return pd.read_sql_query(
            """
            SELECT *
            FROM risk_records
            ORDER BY id DESC
            """,
            conn
        )


# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.title(
    "🛡️ SAP CostShield AI"
)

st.sidebar.caption(
    "Enterprise Supply Chain Control Tower"
)

page = st.sidebar.radio(

    "NAVIGATION",

    [
        "Executive Dashboard",
        "Live Monitoring",
        "AI Risk Prediction",
        "Dynamic Rerouting",
        "SAP Purchase Orders",
        "Supplier Intelligence",
        "Port & Logistics",
        "Alerts & Actions",
        "System Settings"
    ]
)

st.sidebar.divider()

auto_refresh = st.sidebar.toggle(
    "🔄 Auto Refresh",
    value=False
)

refresh_seconds = st.sidebar.slider(
    "Refresh Interval",
    min_value=15,
    max_value=300,
    value=max(
        15,
        min(
            300,
            DEFAULT_REFRESH
        )
    ),
    step=15
)

if st.sidebar.button(
    "Refresh Now",
    use_container_width=True
):

    st.cache_data.clear()
    st.rerun()


# ============================================================
# GLOBAL HEADER
# ============================================================

now = datetime.now().strftime(
    "%d-%m-%Y %H:%M:%S"
)

st.markdown(
    f"""
    <div class="hero">

    <h1>🛡️ SAP CostShield AI</h1>

    <div class="muted">
    AI-POWERED SUPPLY PROCUREMENT & RISK CONTROL TOWER
    </div>

    <br>

    🟢 Monitoring Engine Active
    &nbsp;&nbsp;|&nbsp;&nbsp;
    Last refresh: {now}

    </div>
    """,
    unsafe_allow_html=True
)


# ============================================================
# 1. EXECUTIVE DASHBOARD
# ============================================================

if page == "Executive Dashboard":

    st.title(
        "Executive Command Center"
    )

    risks = get_risks()

    with db_connection() as conn:

        suppliers = pd.read_sql_query(
            """
            SELECT *
            FROM suppliers
            ORDER BY reliability DESC
            """,
            conn
        )

    critical = (
        int(
            (
                risks["status"]
                == "CRITICAL"
            ).sum()
        )
        if not risks.empty
        else 0
    )

    elevated = (
        int(
            (
                risks["status"]
                == "ELEVATED"
            ).sum()
        )
        if not risks.empty
        else 0
    )

    average_risk = (
        round(
            risks["risk_score"].mean(),
            1
        )
        if not risks.empty
        else 0
    )

    c1, c2, c3, c4, c5 = st.columns(5)

    c1.metric(
        "Risk Assessments",
        len(risks)
    )

    c2.metric(
        "Critical",
        critical
    )

    c3.metric(
        "Elevated",
        elevated
    )

    c4.metric(
        "Average Risk",
        average_risk
    )

    c5.metric(
        "Suppliers",
        len(suppliers)
    )

    st.divider()

    st.subheader(
        "Integration Health"
    )

    h1, h2, h3, h4, h5 = st.columns(5)

    h1.metric(
        "SAP S/4HANA",
        "CONNECTED"
        if sap_configured()
        else "NOT CONFIGURED"
    )

    h2.metric(
        "Weather",
        "CONNECTED"
        if OPENWEATHER_API_KEY
        else "NOT CONFIGURED"
    )

    h3.metric(
        "Traffic",
        "CONNECTED"
        if GOOGLE_ROUTES_API_KEY
        else "NOT CONFIGURED"
    )

    h4.metric(
        "Supplier/MES",
        "CONNECTED"
        if SUPPLIER_API_URL
        else "NOT CONFIGURED"
    )

    h5.metric(
        "Port/AIS",
        "CONNECTED"
        if PORT_API_URL
        else "NOT CONFIGURED"
    )

    if not risks.empty:

        st.subheader(
            "Risk Trend"
        )

        st.line_chart(
            risks
            .sort_values("id")
            .set_index("id")
            ["risk_score"]
        )

        st.subheader(
            "Recent Risk Assessments"
        )

        st.dataframe(
            risks.head(20),
            use_container_width=True,
            hide_index=True
        )


# ============================================================
# 2. LIVE MONITORING
# ============================================================

elif page == "Live Monitoring":

    st.title(
        "📡 Live Supply Chain Monitoring"
    )

    st.caption(
        "Weather • Traffic • Factory • Port/AIS"
    )

    c1, c2, c3 = st.columns(3)

    c1.metric(
        "Monitoring",
        "LIVE"
    )

    c2.metric(
        "Refresh",
        f"{refresh_seconds}s"
    )

    c3.metric(
        "Update",
        datetime.now().strftime(
            "%H:%M:%S"
        )
    )

    st.divider()

    # ========================================================
    # WEATHER
    # ========================================================

    st.subheader(
        "🌦️ Weather Intelligence"
    )

    weather_city = st.text_input(
        "Monitoring Location",
        "Pune,IN"
    )

    weather = get_weather(
        weather_city
    )

    weather_risk_value = 0

    if weather.get("connected"):

        weather_risk_value = weather_to_risk(
            weather
        )

        st.success(
            "🟢 LIVE Weather Connected"
        )

        w1, w2, w3, w4 = st.columns(4)

        w1.metric(
            "Temperature",
            f'{weather["temperature"]:.1f} °C'
        )

        w2.metric(
            "Humidity",
            f'{weather["humidity"]}%'
        )

        w3.metric(
            "Wind",
            f'{weather["wind"]:.1f} m/s'
        )

        w4.metric(
            "Weather Risk",
            f"{weather_risk_value}/100"
        )

        st.caption(
            f'Condition: {weather["condition"].title()}'
        )

    else:

        st.warning(
            weather.get(
                "message",
                "Weather API unavailable."
            )
        )

    st.divider()

    # ========================================================
    # TRAFFIC
    # ========================================================

    st.subheader(
        "🚦 Traffic & Route Intelligence"
    )

    tc1, tc2 = st.columns(2)

    with tc1:

        origin = st.text_input(
            "Origin",
            "Mumbai, India"
        )

    with tc2:

        destination = st.text_input(
            "Destination",
            "Pune, India"
        )

    traffic_risk_value = 0

    if st.button(
        "Calculate Live Traffic",
        use_container_width=True
    ):

        try:

            route = calculate_route(
                origin,
                destination
            )

            traffic_risk_value = traffic_risk(
                route
            )

            t1, t2, t3, t4 = st.columns(4)

            t1.metric(
                "Distance",
                f'{route["distanceMeters"] / 1000:.1f} km'
            )

            t2.metric(
                "Live ETA",
                route.get(
                    "duration",
                    "N/A"
                )
            )

            t3.metric(
                "Normal ETA",
                route.get(
                    "staticDuration",
                    "N/A"
                )
            )

            t4.metric(
                "Traffic Risk",
                f"{traffic_risk_value:.1f}/100"
            )

            if traffic_risk_value >= 70:

                st.error(
                    "🔴 Critical traffic congestion."
                )

            elif traffic_risk_value >= 40:

                st.warning(
                    "🟠 Elevated traffic congestion."
                )

            else:

                st.success(
                    "🟢 Traffic conditions acceptable."
                )

            log_event(
                "Google Routes",
                "traffic_risk",
                traffic_risk_value,
                "CONNECTED",
                f"{origin} -> {destination}"
            )

        except Exception as error:

            st.error(
                f"Traffic API error: {error}"
            )

    st.divider()

    # ========================================================
    # FACTORY
    # ========================================================

    st.subheader(
        "🏭 Supplier Factory Capacity"
    )

    factory_df, factory_message = (
        get_supplier_capacity()
    )

    factory_risk_value = 0

    if not factory_df.empty:

        st.success(
            "🟢 LIVE Supplier/MES Connected"
        )

        if "Capacity (%)" in factory_df.columns:

            average_capacity = (
                factory_df["Capacity (%)"]
                .mean()
            )

            factory_risk_value = max(
                0,
                100 - average_capacity
            )

            f1, f2, f3 = st.columns(3)

            f1.metric(
                "Suppliers",
                len(factory_df)
            )

            f2.metric(
                "Average Capacity",
                f"{average_capacity:.1f}%"
            )

            f3.metric(
                "Factory Risk",
                f"{factory_risk_value:.1f}/100"
            )

            st.bar_chart(
                factory_df.set_index(
                    "Supplier"
                )["Capacity (%)"]
            )

        st.dataframe(
            factory_df,
            use_container_width=True,
            hide_index=True
        )

    else:

        st.info(
            factory_message
        )

    st.divider()

    # ========================================================
    # PORT
    # ========================================================

    st.subheader(
        "⚓ Port & AIS Intelligence"
    )

    port_df, port_message = (
        get_port_status()
    )

    port_risk_value = 0

    if not port_df.empty:

        st.success(
            "🟢 LIVE Port/AIS Connected"
        )

        if "Congestion" in port_df.columns:

            port_risk_value = min(
                100,
                max(
                    0,
                    port_df["Congestion"].mean()
                )
            )

        p1, p2, p3 = st.columns(3)

        p1.metric(
            "Ports",
            len(port_df)
        )

        p2.metric(
            "Port Risk",
            f"{port_risk_value:.1f}/100"
        )

        if "Vessels Waiting" in port_df.columns:

            p3.metric(
                "Vessels Waiting",
                int(
                    port_df[
                        "Vessels Waiting"
                    ].sum()
                )
            )

        if (
            "Port" in port_df.columns
            and "Congestion" in port_df.columns
        ):

            st.bar_chart(
                port_df.set_index(
                    "Port"
                )["Congestion"]
            )

        st.dataframe(
            port_df,
            use_container_width=True,
            hide_index=True
        )

    else:

        st.info(
            port_message
        )

    st.divider()

    # ========================================================
    # OVERALL LIVE RISK
    # ========================================================

    st.subheader(
        "🧠 Overall Live Supply Chain Risk"
    )

    overall_risk = round(

        weather_risk_value * 0.25

        + traffic_risk_value * 0.25

        + factory_risk_value * 0.25

        + port_risk_value * 0.25,

        1
    )

    r1, r2, r3, r4, r5 = st.columns(5)

    r1.metric(
        "Overall",
        f"{overall_risk}/100"
    )

    r2.metric(
        "Weather",
        f"{weather_risk_value:.1f}"
    )

    r3.metric(
        "Traffic",
        f"{traffic_risk_value:.1f}"
    )

    r4.metric(
        "Factory",
        f"{factory_risk_value:.1f}"
    )

    r5.metric(
        "Port",
        f"{port_risk_value:.1f}"
    )

    if overall_risk >= 70:

        st.error(
            "🔴 CRITICAL — Immediate supply-chain action required."
        )

        create_alert(
            "CRITICAL",
            "Live Monitoring",
            f"Overall live risk reached {overall_risk}/100."
        )

    elif overall_risk >= 45:

        st.warning(
            "🟠 ELEVATED — Active monitoring and mitigation recommended."
        )

    else:

        st.success(
            "🟢 STABLE — Current live conditions acceptable."
        )


# ============================================================
# 3. AI RISK PREDICTION
# ============================================================

elif page == "AI Risk Prediction":

    st.title(
        "🤖 AI Risk Prediction Engine"
    )

    st.caption(
        "Multi-factor supply chain risk scoring."
    )

    with st.form(
        "risk_prediction"
    ):

        left, right = st.columns(2)

        with left:

            traffic = st.slider(
                "Traffic Risk",
                0,
                100,
                20
            )

            weather = st.slider(
                "Weather Risk",
                0,
                100,
                20
            )

            factory = st.slider(
                "Factory Capacity (%)",
                0,
                100,
                90
            )

            port = st.slider(
                "Port Risk",
                0,
                100,
                20
            )

        with right:

            geopolitical = st.slider(
                "Geopolitical Risk",
                0,
                100,
                20
            )

            route = st.slider(
                "Route Risk",
                0,
                100,
                20
            )

            inventory = st.number_input(
                "Inventory Buffer (Days)",
                min_value=0.0,
                value=7.0
            )

        submit = st.form_submit_button(
            "Analyze Risk",
            use_container_width=True
        )

    if submit:

        inputs = {

            "traffic":
                traffic,

            "weather":
                weather,

            "factory":
                factory,

            "port":
                port,

            "geopolitical":
                geopolitical,

            "route":
                route,

            "inventory":
                inventory
        }

        result = calculate_risk(
            inputs
        )

        save_risk(
            inputs,
            result
        )

        a, b, c = st.columns(3)

        a.metric(
            "Risk Score",
            result["risk_score"]
        )

        b.metric(
            "Status",
            result["status"]
        )

        c.metric(
            "Predicted Delay",
            f'{result["delay"]:.2f} hrs'
        )

        if result["status"] == "CRITICAL":

            st.error(
                "🔴 Critical intervention required."
            )

        elif result["status"] == "ELEVATED":

            st.warning(
                "🟠 Elevated risk. Mitigation recommended."
            )

        else:

            st.success(
                "🟢 Supply chain stable."
            )


# ============================================================
# 4. DYNAMIC REROUTING
# ============================================================

elif page == "Dynamic Rerouting":

    st.title(
        "🚚 Dynamic Route Intelligence"
    )

    origin = st.text_input(
        "Origin",
        "Mumbai, India"
    )

    destination = st.text_input(
        "Destination",
        "Pune, India"
    )

    if st.button(
        "Analyze Route",
        use_container_width=True
    ):

        try:

            route = calculate_route(
                origin,
                destination
            )

            risk = traffic_risk(
                route
            )

            c1, c2, c3 = st.columns(3)

            c1.metric(
                "Distance",
                f'{route["distanceMeters"] / 1000:.1f} km'
            )

            c2.metric(
                "Live ETA",
                route["duration"]
            )

            c3.metric(
                "Traffic Risk",
                f"{risk:.1f}/100"
            )

            if risk >= 70:

                st.error(
                    "🔴 Route requires immediate review."
                )

            elif risk >= 40:

                st.warning(
                    "🟠 Route has elevated congestion."
                )

            else:

                st.success(
                    "🟢 Route currently acceptable."
                )

        except Exception as error:

            st.error(
                str(error)
            )


# ============================================================
# 5. SAP PURCHASE ORDERS
# ============================================================

elif page == "SAP Purchase Orders":

    st.title(
        "🧾 SAP S/4HANA Purchase Orders"
    )

    if not sap_configured():

        st.warning(
            "SAP S/4HANA is not configured."
        )

        st.code(
            """
SAP_BASE_URL = "https://YOUR-SAP-HOST"
SAP_USERNAME = "YOUR_USER"
SAP_PASSWORD = "YOUR_PASSWORD"

# Or OAuth/Bearer:
SAP_TOKEN = "YOUR_TOKEN"
            """
        )

    else:

        po_df, message = (
            get_sap_purchase_orders()
        )

        if not po_df.empty:

            st.success(
                message
            )

            c1, c2 = st.columns(2)

            c1.metric(
                "Purchase Orders",
                len(po_df)
            )

            c2.metric(
                "Total Order Value",
                f'{po_df["Order Value"].sum():,.2f}'
            )

            st.dataframe(
                po_df,
                use_container_width=True,
                hide_index=True
            )

        else:

            st.error(
                message
            )


# ============================================================
# 6. SUPPLIER INTELLIGENCE
# ============================================================

elif page == "Supplier Intelligence":

    st.title(
        "🏭 Supplier Intelligence"
    )

    with st.form(
        "supplier_form"
    ):

        name = st.text_input(
            "Supplier Name"
        )

        location = st.text_input(
            "Location"
        )

        reliability = st.slider(
            "Reliability (%)",
            0,
            100,
            90
        )

        lead_time = st.number_input(
            "Lead Time (Days)",
            min_value=0.0,
            value=5.0
        )

        cost = st.number_input(
            "Supply Cost",
            min_value=0.0
        )

        capacity = st.slider(
            "Factory Capacity (%)",
            0,
            100,
            90
        )

        submit = st.form_submit_button(
            "Save Supplier",
            use_container_width=True
        )

    if submit:

        if not name:

            st.error(
                "Supplier name is required."
            )

        else:

            with db_connection() as conn:

                conn.execute(
                    """
                    INSERT INTO suppliers
                    (
                        name,
                        location,
                        reliability,
                        lead_time,
                        cost,
                        capacity_pct
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        name,
                        location,
                        reliability,
                        lead_time,
                        cost,
                        capacity
                    )
                )

                conn.commit()

            st.success(
                "Supplier saved."
            )

    with db_connection() as conn:

        supplier_df = pd.read_sql_query(
            """
            SELECT *
            FROM suppliers
            ORDER BY reliability DESC
            """,
            conn
        )

    if not supplier_df.empty:

        st.dataframe(
            supplier_df,
            use_container_width=True,
            hide_index=True
        )

        st.bar_chart(
            supplier_df.set_index(
                "name"
            )["reliability"]
        )


# ============================================================
# 7. PORT & LOGISTICS
# ============================================================

elif page == "Port & Logistics":

    st.title(
        "⚓ Port & Logistics"
    )

    port_df, message = (
        get_port_status()
    )

    if not port_df.empty:

        st.success(
            "🟢 Live Port/AIS data connected."
        )

        st.dataframe(
            port_df,
            use_container_width=True,
            hide_index=True
        )

        if (
            "Port" in port_df.columns
            and "Congestion" in port_df.columns
        ):

            st.bar_chart(
                port_df.set_index(
                    "Port"
                )["Congestion"]
            )

    else:

        st.info(
            message
        )


# ============================================================
# 8. ALERTS & ACTIONS
# ============================================================

elif page == "Alerts & Actions":

    st.title(
        "🚨 Alerts & Recommended Actions"
    )

    with db_connection() as conn:

        alerts_df = pd.read_sql_query(
            """
            SELECT *
            FROM alerts
            ORDER BY id DESC
            LIMIT 100
            """,
            conn
        )

    if alerts_df.empty:

        st.success(
            "🟢 No alerts recorded."
        )

    else:

        critical = alerts_df[
            alerts_df["severity"]
            == "CRITICAL"
        ]

        st.metric(
            "Critical Alerts",
            len(critical)
        )

        st.dataframe(
            alerts_df,
            use_container_width=True,
            hide_index=True
        )

        st.subheader(
            "Recommended Actions"
        )

        st.markdown(
            """
            **For Critical Risk**

            1. Check affected purchase orders.
            2. Contact supplier immediately.
            3. Evaluate alternate supplier.
            4. Evaluate alternate route.
            5. Protect minimum inventory.
            6. Escalate procurement decision.

            **For Elevated Risk**

            1. Increase monitoring frequency.
            2. Confirm supplier production status.
            3. Review ETA.
            4. Check port congestion.
            5. Prepare contingency route.
            """
        )


# ============================================================
# 9. SYSTEM SETTINGS
# ============================================================

elif page == "System Settings":

    st.title(
        "⚙️ System & Integration Health"
    )

    integrations = {

        "SAP S/4HANA":
            sap_configured(),

        "OpenWeather":
            bool(
                OPENWEATHER_API_KEY
            ),

        "Google Routes":
            bool(
                GOOGLE_ROUTES_API_KEY
            ),

        "Supplier / MES":
            bool(
                SUPPLIER_API_URL
            ),

        "Port / AIS":
            bool(
                PORT_API_URL
            )
    }

    for name, connected in integrations.items():

        if connected:

            st.success(
                f"🟢 {name}: CONFIGURED"
            )

        else:

            st.warning(
                f"🟠 {name}: NOT CONFIGURED"
            )

    st.divider()

    st.subheader(
        "Required Secrets"
    )

    st.code(
        """
OPENWEATHER_API_KEY = "YOUR_KEY"

GOOGLE_ROUTES_API_KEY = "YOUR_KEY"

SAP_BASE_URL = "https://YOUR-SAP-HOST"
SAP_USERNAME = "YOUR_USER"
SAP_PASSWORD = "YOUR_PASSWORD"

# OR
SAP_TOKEN = "YOUR_TOKEN"

SUPPLIER_API_URL = "https://YOUR-SUPPLIER-API/capacity"
SUPPLIER_API_TOKEN = "YOUR_TOKEN"

PORT_API_URL = "https://YOUR-PORT-API/status"
PORT_API_TOKEN = "YOUR_TOKEN"

REFRESH_SECONDS = "60"
        """
    )

    st.divider()

    st.subheader(
        "Database"
    )

    try:

        with db_connection() as conn:

            risk_count = conn.execute(
                "SELECT COUNT(*) FROM risk_records"
            ).fetchone()[0]

            supplier_count = conn.execute(
                "SELECT COUNT(*) FROM suppliers"
            ).fetchone()[0]

            alert_count = conn.execute(
                "SELECT COUNT(*) FROM alerts"
            ).fetchone()[0]

        c1, c2, c3 = st.columns(3)

        c1.metric(
            "Risk Records",
            risk_count
        )

        c2.metric(
            "Suppliers",
            supplier_count
        )

        c3.metric(
            "Alerts",
            alert_count
        )

        st.success(
            "🟢 Local database operational."
        )

    except Exception as error:

        st.error(
            f"Database error: {error}"
        )


# ============================================================
# AUTO REFRESH
# ============================================================

if auto_refresh:

    time.sleep(
        refresh_seconds
    )

    st.cache_data.clear()

    st.rerun()
```

### `requirements.txt`

```txt id="69104"
streamlit
pandas
requests
```

### Streamlit Secrets

```toml id="72618"
OPENWEATHER_API_KEY = "YOUR_OPENWEATHER_KEY"
GOOGLE_ROUTES_API_KEY = "YOUR_GOOGLE_ROUTES_KEY"

SAP_BASE_URL = "https://YOUR-SAP-HOST"
SAP_USERNAME = "YOUR_SAP_USERNAME"
SAP_PASSWORD = "YOUR_SAP_PASSWORD"

# Alternatively use:
# SAP_TOKEN = "YOUR_SAP_TOKEN"

SUPPLIER_API_URL = "https://YOUR-SUPPLIER-API/capacity"
SUPPLIER_API_TOKEN = "YOUR_SUPPLIER_TOKEN"

PORT_API_URL = "https://YOUR-PORT-API/status"
PORT_API_TOKEN = "YOUR_PORT_TOKEN"

REFRESH_SECONDS = "60"
```
