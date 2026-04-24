import streamlit as st
import pandas as pd
import json
import re
import io
import base64
import csv
import os
from datetime import datetime, time
import pdfplumber
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage, HRFlowable
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
import tempfile

st.set_page_config(
    page_title="Peek-a-Bill — your calls, caught red-handed",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── Palette ──────────────────────────────────────────────────────────────────
PINK      = "#D4849E"
PINK_L    = "#F7E8EE"
PINK_M    = "#EFC8D8"
PINK_D    = "#A85C76"
GREEN     = "#6A9E62"
GREEN_L   = "#D8EDD2"
GREEN_BG  = "#F2F7F0"
WHITE     = "#FFFFFF"
BG        = "#FBF5F7"
TXT       = "#2A1F24"
MUTED     = "#7A6068"
HINT      = "#B89EA8"
BORDER    = "#EDD8E2"
ALERT_R   = "#F7C1C1"
ALERT_RT  = "#A32D2D"
ALERT_Y   = "#FAC775"
ALERT_YT  = "#633806"
ALERT_G   = GREEN_L
ALERT_GT  = "#27500A"

TELECOM_MCC_MNC = {
    "Airtel":       [("404","10"),("404","20"),("405","51"),("405","52")],
    "Jio":          [("404","02"),("405","857"),("405","858")],
    "Vodafone/Vi":  [("404","20"),("404","43"),("405","67")],
    "BSNL":         [("404","01"),("404","07"),("405","09")],
    "Other":        [],
}

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;700&family=Inter:wght@300;400;500;600&display=swap');
html,body,[class*="css"]{{font-family:'Inter',sans-serif;background:{BG};color:{TXT};}}
[data-testid="stSidebar"]{{background-color:#FDF6F8!important;border-right:1px solid {BORDER}!important;}}
[data-testid="stSidebar"] .block-container{{padding-top:1rem!important;}}
.brand-name{{font-family:'Playfair Display',Georgia,serif;font-size:26px;font-weight:700;color:{PINK_D};letter-spacing:-0.5px;margin:0;line-height:1.2;}}
.brand-tagline{{font-size:11px;color:{HINT};margin-top:3px;letter-spacing:0.3px;margin-bottom:0;}}
.section-header{{font-size:11px;font-weight:700;letter-spacing:1.4px;color:{HINT};text-transform:uppercase;margin:18px 0 6px 0;padding:0;}}
.page-title{{font-family:'Playfair Display',serif;font-size:22px;font-weight:700;color:{TXT};margin:0;}}
.page-sub{{font-size:12px;color:{HINT};margin-top:3px;}}
.card{{background:{WHITE};border:1px solid {BORDER};border-radius:12px;padding:18px 20px;margin-bottom:14px;}}
.info-pill{{background:{PINK_L};color:{PINK_D};font-size:10px;font-weight:700;padding:3px 10px;border-radius:20px;display:inline-block;}}
.green-pill{{background:{GREEN_L};color:{GREEN};font-size:10px;font-weight:700;padding:3px 10px;border-radius:20px;display:inline-block;}}
.ai-badge{{background:{GREEN_L};border:1px solid #C0DD97;border-radius:10px;padding:10px 14px;font-size:11px;color:#3E6E38;line-height:1.6;margin-top:12px;}}
.alert-red{{background:{ALERT_R};border:1px solid #F09595;border-radius:10px;padding:12px 16px;color:{ALERT_RT};font-size:12px;margin-bottom:10px;}}
.alert-yellow{{background:#FAEEDA;border:1px solid {ALERT_Y};border-radius:10px;padding:12px 16px;color:{ALERT_YT};font-size:12px;margin-bottom:10px;}}
.alert-green{{background:{ALERT_G};border:1px solid #A8CE9E;border-radius:10px;padding:12px 16px;color:{ALERT_GT};font-size:12px;margin-bottom:10px;}}
.stButton>button{{background:{PINK}!important;color:white!important;border:none!important;border-radius:8px!important;font-weight:600!important;font-size:12px!important;padding:8px 20px!important;}}
.stButton>button:hover{{background:{PINK_D}!important;}}
.stDownloadButton>button{{background:transparent!important;color:{PINK_D}!important;border:1px solid {BORDER}!important;border-radius:8px!important;font-weight:600!important;font-size:11px!important;}}
div[data-testid="metric-container"]{{background:{WHITE};border:1px solid {BORDER};border-radius:12px;padding:14px 16px;}}
.stTabs [data-baseweb="tab"]{{font-size:12px;font-weight:600;color:{MUTED};}}
.stTabs [aria-selected="true"]{{color:{PINK_D}!important;border-bottom-color:{PINK}!important;}}
.stTextInput>div>input{{border:1px solid {BORDER}!important;border-radius:8px!important;background:{WHITE}!important;font-size:13px;}}
.compare-col{{background:{WHITE};border:1px solid {BORDER};border-radius:12px;padding:16px;}}
.device-card{{background:{GREEN_BG};border:1px solid {GREEN_L};border-radius:12px;padding:14px 16px;margin-bottom:10px;}}
.device-label{{font-size:9px;font-weight:700;letter-spacing:0.6px;text-transform:uppercase;color:{GREEN};margin-bottom:3px;}}
.device-val{{font-size:14px;font-weight:600;color:#3E6E38;}}
.footer-note{{font-size:10px;color:{HINT};text-align:center;margin-top:24px;padding:12px;border-top:1px solid {BORDER};}}
</style>
""", unsafe_allow_html=True)

# ── Session state ─────────────────────────────────────────────────────────────
for k, v in [
    ("bill_data", None), ("df_calls", None), ("meta", {}),
    ("bill_data_2", None), ("df_calls_2", None), ("meta_2", {}),
    ("df_data_sessions", None),
    ("page", "upload"),
]:
    if k not in st.session_state:
        st.session_state[k] = v
import re

def extract_calls_from_tables(pdf):
    """
    Table-based extractor. Handles:
      - Standard rows with a 10-digit number
      - Jio CDR rows: optional 91 prefix, DD-MON-YYYY date, time, masked number (91xxxxxxxx6),
        then usage columns: Used Usage, Billed Usage, Free Usage, Chargeable Usage, Amount
        e.g.: 91 05-MAR-2026 08:42:51 919xxxxxxxx6 110 0 0 0 0.00
    """
    records = []
    data_sessions = []

    # Jio CDR call row: optional seq/country, DD-MON-YYYY, HH:MM:SS, number (may be masked), usage cols
    jio_call_pat = re.compile(
        r'(?:91\s+)?'
        r'(\d{1,2}[-\/][A-Za-z]{3}[-\/]\d{2,4})\s+'
        r'(\d{1,2}:\d{2}:\d{2})\s+'
        r'((?:91)?[6-9X*x\d]{6,13})\s+'
        r'(\d+)\s+([\d\.]+)\s+([\d\.]+)\s+([\d\.]+)\s+([\d\.]+)',
        re.I
    )

    for page in pdf.pages:
        tables = page.extract_tables()
        if not tables:
            continue

        for table in tables:
            # Detect header row to understand column layout
            header_map = {}
            header_row_idx = -1
            for ri, row in enumerate(table):
                if not row:
                    continue
                row_lower = [str(c).lower().strip() if c else "" for c in row]
                if any(k in " ".join(row_lower) for k in ["used usage","billed usage","chargeable","called number","destination"]):
                    header_map = {v: i for i, v in enumerate(row_lower) if v}
                    header_row_idx = ri
                    break

            for ri, row in enumerate(table):
                if not row or ri == header_row_idx:
                    continue

                row_text = " ".join([str(x) for x in row if x])

                # ── Try Jio CDR call format first ──────────────────────────
                jm = jio_call_pat.search(row_text)
                if jm:
                    raw_num = re.sub(r'\D', '', jm.group(3))
                    number = raw_num[-10:] if len(raw_num) >= 10 else raw_num
                    used   = float(jm.group(5)) if jm.group(5) else 0
                    records.append({
                        "call_date":         jm.group(1),
                        "start_time":        jm.group(2),
                        "end_time":          "",
                        "called_number":     number,
                        "talk_time_seconds": int(jm.group(4)),
                        "used_usage":        used,
                        "billed_usage":      float(jm.group(6)),
                        "free_usage":        float(jm.group(7)),
                        "chargeable_usage":  float(jm.group(8)),
                    })
                    continue

                # ── Standard call row ──────────────────────────────────────
                num_match  = re.search(r'(\+?91)?([6-9]\d{9})', row_text)
                date_match = re.search(r'\d{1,2}[-/][A-Za-z0-9]+[-/]\d{2,4}', row_text)
                time_matches = re.findall(r'\d{1,2}:\d{2}(?::\d{2})?', row_text)
                dur_match  = re.search(r'(\d+)\s*(sec|s|mins|min|m)\b', row_text, re.I)

                if num_match and date_match:
                    duration = 0
                    if dur_match:
                        val  = int(dur_match.group(1))
                        unit = dur_match.group(2).lower()
                        duration = val * 60 if 'm' in unit else val
                    number = (num_match.group(2) or re.sub(r'\D','',num_match.group()))[-10:]
                    records.append({
                        "call_date":         date_match.group(),
                        "start_time":        time_matches[0] if time_matches else "",
                        "end_time":          time_matches[1] if len(time_matches) > 1 else "",
                        "called_number":     number,
                        "talk_time_seconds": duration,
                    })

    return records, data_sessions
# ── Helpers ───────────────────────────────────────────────────────────────────

def clean_number(s):
    return re.sub(r'[^\d+]', '', str(s))

def extract_bill_data(pdf_file):
    data = {
        "account_info": {}, "statement_info": {}, "billing_info": {},
        "plan_details": {}, "payment_history": [], "weekly_data": [],
        "call_records": [], "sms_records": [], "data_session_records": [],
        "device_info": {}, "raw_text": ""
    }
    try:
        with pdfplumber.open(pdf_file) as pdf:
            full_text = ""
            for page in pdf.pages:
                full_text += (page.extract_text() or "") + "\n"
            data["raw_text"] = full_text
            T = full_text

            # ── Table-based extraction (catches Jio CDR tables) ───────────
            tbl_calls, tbl_sessions = extract_calls_from_tables(pdf)
            data["call_records"].extend(tbl_calls)
            data["data_session_records"].extend(tbl_sessions)

            # Phone
            m = re.search(r'(?:mobile|phone|number|no\.?)[:\s]+([6-9]\d{9})', T, re.I)
            if not m: m = re.search(r'\b([6-9]\d{9})\b', T)
            if m: data["account_info"]["phone_number"] = m.group(1)

            # Address
            m = re.search(r'(?:address|bill to|billed to)[:\s]+(.+?)(?:\n|statement|account)', T, re.I|re.S)
            if m: data["account_info"]["address"] = re.sub(r'\s+',' ',m.group(1).strip())[:200]

            # Statement
            m = re.search(r'(?:statement|bill)\s*(?:number|no\.?|#)[:\s]+([A-Z0-9\-\/]+)', T, re.I)
            if m: data["statement_info"]["statement_number"] = m.group(1)

            # Date
            m = re.search(r'(?:bill date|statement date|date)[:\s]+(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})', T, re.I)
            if m: data["statement_info"]["bill_date"] = m.group(1)

            # Balance
            m = re.search(r'(?:previous|last|opening)\s*balance[:\s]+(?:Rs\.?|INR|₹)?\s*([\d,]+\.?\d*)', T, re.I)
            if m: data["billing_info"]["previous_balance"] = m.group(1).replace(',','')

            # Amount
            m = re.search(r'(?:amount\s*(?:due|payable|to\s*pay)|total\s*due|net\s*payable)[:\s]+(?:Rs\.?|INR|₹)?\s*([\d,]+\.?\d*)', T, re.I)
            if m: data["billing_info"]["amount_payable"] = m.group(1).replace(',','')

            # Plan
            m = re.search(r'(?:plan|tariff|pack)[:\s]+([^\n]+)', T, re.I)
            if m: data["plan_details"]["plan_name"] = m.group(1).strip()[:100]

            # Telecom provider auto-detection
            telecom_hints = {
                "Jio":         ["jio", "reliance jio", "jionet", "ril"],
                "Airtel":      ["airtel", "bharti airtel"],
                "Vodafone/Vi": ["vodafone", "vi ", "idea", "vodafone idea"],
                "BSNL":        ["bsnl", "bharat sanchar"],
                "MTNL":        ["mtnl"],
            }
            T_lower = T.lower()
            for provider, hints in telecom_hints.items():
                if any(h in T_lower for h in hints):
                    data["account_info"]["telecom_provider"] = provider
                    break

            # ── Call records ──────────────────────────────────────────────
            # Format A: standard CDR with date/time/number/duration
            call_pat = re.compile(
                r'(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})\s+'
                r'(\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AP]M)?)\s+'
                r'(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})?\s*'
                r'(\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AP]M)?)?\s+'
                r'([6-9]\d{9}|0\d{10}|\+91\d{10})\s+'
                r'(\d+)', re.I)
            for m2 in call_pat.finditer(T):
                data["call_records"].append({
                    "call_date": m2.group(1), "start_time": m2.group(2),
                    "end_date": m2.group(3) or m2.group(1), "end_time": m2.group(4) or "",
                    "called_number": m2.group(5), "talk_time_seconds": int(m2.group(6))
                })

            # Format B: Jio CDR call row
            # Optional leading seq/country (91), DD-MON-YYYY, HH:MM:SS, masked/full number, duration, usage cols
            # e.g.: 91 05-MAR-2026 08:42:51 919xxxxxxxx6 110 0 0 0 0.00
            jio_call_pat = re.compile(
                r'(?:91\s+)?'
                r'(\d{1,2}[-\/][A-Za-z]{3}[-\/]\d{2,4})\s+'
                r'(\d{1,2}:\d{2}:\d{2})\s+'
                r'((?:91)?[6-9X*x\d]{6,13})\s+'
                r'(\d+)\s+([\d\.]+)\s+([\d\.]+)\s+([\d\.]+)\s+([\d\.]+)',
                re.I
            )
            seen_jio = set()
            for m2 in jio_call_pat.finditer(T):
                key = (m2.group(1), m2.group(2), m2.group(3))
                if key in seen_jio:
                    continue
                seen_jio.add(key)
                raw_num = re.sub(r'\D', '', m2.group(3))
                number  = raw_num[-10:] if len(raw_num) >= 10 else raw_num
                data["call_records"].append({
                    "call_date":         m2.group(1),
                    "start_time":        m2.group(2),
                    "end_date":          m2.group(1),
                    "end_time":          "",
                    "called_number":     number,
                    "talk_time_seconds": int(m2.group(4)),
                    "used_usage":        float(m2.group(5)),
                    "billed_usage":      float(m2.group(6)),
                    "free_usage":        float(m2.group(7)),
                    "chargeable_usage":  float(m2.group(8)),
                })

            # Jio data session records
            # Format: <seq> <date> <start_time> <date> <end_time> <destination> <vol1> <vol2> <total_vol> <charged> <charge>
            # e.g.: 44 02-MAR-2026 12:43:29 02-MAR-2026 13:54:35 JIONET 9.668 9.668 9.668 0.000 0.0
            data_pat = re.compile(
                r'\d+\s+'
                r'(\d{1,2}[-\/][A-Za-z]{3}[-\/]\d{2,4})\s+'
                r'(\d{1,2}:\d{2}:\d{2})\s+'
                r'(\d{1,2}[-\/][A-Za-z]{3}[-\/]\d{2,4})\s+'
                r'(\d{1,2}:\d{2}:\d{2})\s+'
                r'(JIONET|INTERNET|DATA|APN[\w\.]*)\s+'
                r'([\d\.]+)\s+[\d\.]+\s+([\d\.]+)\s+([\d\.]+)\s+([\d\.]+)',
                re.I
            )
            for m2 in data_pat.finditer(T):
                data["data_session_records"].append({
                    "start_date":   m2.group(1),
                    "start_time":   m2.group(2),
                    "end_date":     m2.group(3),
                    "end_time":     m2.group(4),
                    "destination":  m2.group(5).upper(),
                    "upload_mb":    float(m2.group(6)),
                    "total_mb":     float(m2.group(7)),
                    "charged_mb":   float(m2.group(8)),
                    "charge":       float(m2.group(9)),
                })

            # Deduplicate call records (table + text regex may overlap)
            seen_calls = set()
            unique_calls = []
            for r in data["call_records"]:
                key = (r.get("call_date",""), r.get("start_time",""), r.get("called_number",""))
                if key not in seen_calls:
                    seen_calls.add(key)
                    unique_calls.append(r)
            data["call_records"] = unique_calls

            # Deduplicate data sessions
            seen_ds = set()
            unique_ds = []
            for r in data["data_session_records"]:
                key = (r.get("start_date",""), r.get("start_time",""), r.get("destination",""))
                if key not in seen_ds:
                    seen_ds.add(key)
                    unique_ds.append(r)
            data["data_session_records"] = unique_ds

            # SMS records
            sms_pat = re.compile(r'(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})\s+(\d{1,2}:\d{2}(?::\d{2})?)\s+(?:SMS|sms|text)\s+([6-9]\d{9}|\+91\d{10}|\w+)', re.I)
            for m2 in sms_pat.finditer(T):
                data["sms_records"].append({"date": m2.group(1), "time": m2.group(2), "number": m2.group(3)})

            # Device info
            imei = re.search(r'IMEI[:\s]+(\d{15})', T, re.I)
            if imei: data["device_info"]["imei"] = imei.group(1)

            model = re.search(r'(?:device|handset|model)[:\s]+([^\n]+)', T, re.I)
            if model: data["device_info"]["model"] = model.group(1).strip()[:80]

            imsi = re.search(r'IMSI[:\s]+(\d{15})', T, re.I)
            if imsi: data["device_info"]["imsi"] = imsi.group(1)

            os_match = re.search(r'(?:OS|operating system)[:\s]+([^\n]+)', T, re.I)
            if os_match: data["device_info"]["os"] = os_match.group(1).strip()[:60]

    except Exception as e:
        st.warning(f"Extraction note: {e}")
    return data


def parse_manual_calls(text):
    records = []
    for line in text.strip().split('\n'):
        parts = re.split(r'[,\t|]+', line.strip())
        if len(parts) >= 4:
            try:
                records.append({
                    "call_date": parts[0].strip(), "start_time": parts[1].strip(),
                    "end_time": parts[2].strip() if len(parts) > 2 else "",
                    "called_number": parts[3].strip() if len(parts) > 3 else "",
                    "talk_time_seconds": int(re.sub(r'[^\d]','', parts[4])) if len(parts) > 4 else 0
                })
            except: pass
    return records


def get_location(mcc, mnc, cell_id=None, lac=None):
    MCC_DEFAULTS = {"404": (20.5937, 78.9629, "India"), "405": (20.5937, 78.9629, "India")}
    try:
        payload = {"token":"test","radio":"gsm","mcc":int(mcc),"mnc":int(mnc),
                   "cells":[{"lac":int(lac) if lac else 1,"cid":int(cell_id) if cell_id else 1}],"address":1}
        r = requests.post("https://us1.unwiredlabs.com/v2/process.php", json=payload, timeout=4)
        if r.status_code == 200:
            d = r.json()
            if d.get("status") == "ok":
                return d.get("lat"), d.get("lon"), d.get("address",{}).get("city","India")
    except: pass
    if mcc in MCC_DEFAULTS:
        return MCC_DEFAULTS[mcc]
    return None, None, None


def build_charts(df, suffix=""):
    figs = {}
    if df is None or len(df) == 0:
        return figs
    df = df.copy()

    if "called_number" in df.columns and "talk_time_seconds" in df.columns:
        top = df.groupby("called_number").agg(
            total_calls=("call_date","count"),
            total_seconds=("talk_time_seconds","sum")
        ).sort_values("total_calls", ascending=False).head(10).reset_index()
        top["total_minutes"] = (top["total_seconds"]/60).round(1)

        figs["top_numbers"] = px.bar(top, x="total_calls", y="called_number", orientation="h",
            color_discrete_sequence=[PINK], title="Most called numbers",
            labels={"total_calls":"Calls","called_number":"Number"})
        figs["talk_time"] = px.bar(top, x="total_minutes", y="called_number", orientation="h",
            color_discrete_sequence=[PINK_M], title="Talk time per number (min)",
            labels={"total_minutes":"Minutes","called_number":"Number"})

    if "call_date" in df.columns:
        try:
            df["parsed_date"] = pd.to_datetime(df["call_date"], dayfirst=True, errors="coerce")
            df["day_of_week"] = df["parsed_date"].dt.day_name()
            day_order = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
            day_c = df.groupby("day_of_week").size().reindex(day_order, fill_value=0).reset_index()
            day_c.columns = ["Day","Calls"]
            figs["day_of_week"] = px.bar(day_c, x="Day", y="Calls",
                color_discrete_sequence=[PINK], title="Calls by day of week")
        except: pass

    if "start_time" in df.columns:
        try:
            df["hour"] = pd.to_datetime(df["start_time"], format="%H:%M:%S", errors="coerce").dt.hour
            if df["hour"].isna().all():
                df["hour"] = pd.to_datetime(df["start_time"], format="%H:%M", errors="coerce").dt.hour
            hc = df.groupby("hour").size().reset_index()
            hc.columns = ["Hour","Calls"]
            figs["hour_of_day"] = px.bar(hc, x="Hour", y="Calls",
                color_discrete_sequence=[GREEN], title="Calls by hour of day")
        except: pass

    if "talk_time_seconds" in df.columns:
        df["talk_minutes"] = df["talk_time_seconds"]/60
        figs["duration_dist"] = px.histogram(df, x="talk_minutes", nbins=20,
            color_discrete_sequence=[PINK_M], title="Call duration distribution (min)")

    for fig in figs.values():
        fig.update_layout(
            plot_bgcolor=WHITE, paper_bgcolor=WHITE, font_family="Inter", font_color=TXT,
            title_font_family="Playfair Display", title_font_size=15,
            margin=dict(l=20,r=20,t=40,b=20),
            xaxis=dict(gridcolor=BORDER), yaxis=dict(gridcolor=BORDER)
        )
    return figs


# ── Suspicious Activity Detection ────────────────────────────────────────────

def detect_suspicious(df, sms_df=None):
    alerts = []
    if df is None or len(df) == 0:
        return alerts

    df = df.copy()

    # Parse hour
    try:
        df["hour"] = pd.to_datetime(df["start_time"], format="%H:%M:%S", errors="coerce").dt.hour
        if df["hour"].isna().all():
            df["hour"] = pd.to_datetime(df["start_time"], format="%H:%M", errors="coerce").dt.hour
    except:
        df["hour"] = None

    # 1. Late-night calls (11pm–5am)
    if "hour" in df.columns and df["hour"].notna().any():
        late = df[df["hour"].between(23, 23) | df["hour"].between(0, 5)]
        if len(late) > 0:
            nums = late["called_number"].value_counts().head(3).to_dict() if "called_number" in late.columns else {}
            num_str = ", ".join([f"{k} ({v}x)" for k,v in nums.items()])
            alerts.append({
                "level": "red",
                "icon": "🌙",
                "title": f"Late-night calls detected ({len(late)} calls between 11 PM – 5 AM)",
                "detail": f"Numbers involved: {num_str}" if num_str else "Check call log for details.",
                "count": len(late)
            })

    # 2. Frequent calls to unknown / short numbers
    if "called_number" in df.columns:
        freq = df["called_number"].value_counts()
        very_freq = freq[freq >= 10]
        if len(very_freq) > 0:
            alerts.append({
                "level": "yellow",
                "icon": "📞",
                "title": f"High-frequency numbers ({len(very_freq)} numbers called 10+ times)",
                "detail": "Numbers: " + ", ".join([f"{k} ({v}x)" for k,v in very_freq.items()]),
                "count": len(very_freq)
            })

        # Short / 4-5 digit numbers (service or suspicious codes)
        short_nums = df[df["called_number"].str.len() <= 5]["called_number"].value_counts()
        if len(short_nums) > 0:
            alerts.append({
                "level": "yellow",
                "icon": "🔢",
                "title": f"Short/service numbers dialled ({len(short_nums)} unique short codes)",
                "detail": "Codes: " + ", ".join(short_nums.index.tolist()[:5]),
                "count": len(short_nums)
            })

    # 3. Very long calls (> 60 min)
    if "talk_time_seconds" in df.columns:
        long_calls = df[df["talk_time_seconds"] > 3600]
        if len(long_calls) > 0:
            alerts.append({
                "level": "yellow",
                "icon": "⏱",
                "title": f"Unusually long calls ({len(long_calls)} calls over 60 minutes)",
                "detail": "Longest: " + str(round(long_calls["talk_time_seconds"].max()/60,1)) + " min to " + (long_calls.loc[long_calls["talk_time_seconds"].idxmax(),"called_number"] if "called_number" in long_calls.columns else "unknown"),
                "count": len(long_calls)
            })

    # 4. Calls on consecutive days to same number
    if "called_number" in df.columns and "parsed_date" in df.columns:
        try:
            suspicious_streak = []
            for num, group in df.groupby("called_number"):
                dates = sorted(group["parsed_date"].dropna().dt.date.unique())
                if len(dates) >= 5:
                    suspicious_streak.append((num, len(dates)))
            if suspicious_streak:
                suspicious_streak.sort(key=lambda x: x[1], reverse=True)
                alerts.append({
                    "level": "yellow",
                    "icon": "📅",
                    "title": f"Numbers called on 5+ different days",
                    "detail": "Frequent contact: " + ", ".join([f"{n} ({d} days)" for n,d in suspicious_streak[:3]]),
                    "count": len(suspicious_streak)
                })
        except: pass

    # 5. High SMS activity
    if sms_df is not None and len(sms_df) > 0:
        if len(sms_df) > 50:
            alerts.append({
                "level": "red",
                "icon": "💬",
                "title": f"High SMS activity detected ({len(sms_df)} SMS records)",
                "detail": "Unusually large number of SMS messages. Check for bulk messaging activity.",
                "count": len(sms_df)
            })
        if "number" in sms_df.columns:
            top_sms = sms_df["number"].value_counts().head(3)
            if len(top_sms) > 0 and top_sms.iloc[0] >= 10:
                alerts.append({
                    "level": "yellow",
                    "icon": "📱",
                    "title": "Repeated SMS to same number",
                    "detail": "Top SMS targets: " + ", ".join([f"{k} ({v}x)" for k,v in top_sms.items()]),
                    "count": int(top_sms.iloc[0])
                })

    # 6. International numbers
    if "called_number" in df.columns:
        intl = df[df["called_number"].str.startswith("+") & ~df["called_number"].str.startswith("+91")]
        if len(intl) > 0:
            alerts.append({
                "level": "red",
                "icon": "🌍",
                "title": f"International calls detected ({len(intl)} calls)",
                "detail": "Numbers: " + ", ".join(intl["called_number"].unique()[:4].tolist()),
                "count": len(intl)
            })

    if not alerts:
        alerts.append({
            "level": "green",
            "icon": "✓",
            "title": "No suspicious activity detected",
            "detail": "All call patterns appear normal based on our checks.",
            "count": 0
        })
    return alerts


# ── Compare two bills ────────────────────────────────────────────────────────

def compare_bills(df1, df2, meta1, meta2):
    figs = {}
    if df1 is None or df2 is None:
        return figs

    # Total calls comparison
    labels = [meta1.get("telecom","Bill 1"), meta2.get("telecom","Bill 2")]
    calls = [len(df1), len(df2)]
    fig_calls = go.Figure(go.Bar(x=labels, y=calls, marker_color=[PINK, GREEN],
        text=calls, textposition="outside"))
    fig_calls.update_layout(title="Total calls comparison",
        plot_bgcolor=WHITE, paper_bgcolor=WHITE, font_family="Inter",
        title_font_family="Playfair Display", title_font_size=15,
        margin=dict(l=20,r=20,t=40,b=20), xaxis=dict(gridcolor=BORDER), yaxis=dict(gridcolor=BORDER))
    figs["total_calls"] = fig_calls

    # Talk time comparison
    t1 = df1["talk_time_seconds"].sum()/3600 if "talk_time_seconds" in df1.columns else 0
    t2 = df2["talk_time_seconds"].sum()/3600 if "talk_time_seconds" in df2.columns else 0
    fig_time = go.Figure(go.Bar(x=labels, y=[round(t1,2), round(t2,2)],
        marker_color=[PINK, GREEN], text=[f"{round(t1,1)}h", f"{round(t2,1)}h"], textposition="outside"))
    fig_time.update_layout(title="Total talk time (hours)",
        plot_bgcolor=WHITE, paper_bgcolor=WHITE, font_family="Inter",
        title_font_family="Playfair Display", title_font_size=15,
        margin=dict(l=20,r=20,t=40,b=20), xaxis=dict(gridcolor=BORDER), yaxis=dict(gridcolor=BORDER))
    figs["talk_time"] = fig_time

    # Day of week overlay
    try:
        day_order = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
        for df_, label_ in [(df1, labels[0]), (df2, labels[1])]:
            df_["parsed_date"] = pd.to_datetime(df_["call_date"], dayfirst=True, errors="coerce")
            df_["day_of_week"] = df_["parsed_date"].dt.day_name()
        d1 = df1.groupby("day_of_week").size().reindex(day_order,fill_value=0)
        d2 = df2.groupby("day_of_week").size().reindex(day_order,fill_value=0)
        fig_days = go.Figure()
        fig_days.add_trace(go.Bar(name=labels[0], x=day_order, y=d1.tolist(), marker_color=PINK))
        fig_days.add_trace(go.Bar(name=labels[1], x=day_order, y=d2.tolist(), marker_color=GREEN))
        fig_days.update_layout(barmode="group", title="Day-of-week activity overlay",
            plot_bgcolor=WHITE, paper_bgcolor=WHITE, font_family="Inter",
            title_font_family="Playfair Display", title_font_size=15,
            margin=dict(l=20,r=20,t=40,b=20))
        figs["day_overlay"] = fig_days
    except: pass

    # Common numbers
    if "called_number" in df1.columns and "called_number" in df2.columns:
        nums1 = set(df1["called_number"].unique())
        nums2 = set(df2["called_number"].unique())
        common = nums1 & nums2
        only1 = nums1 - nums2
        only2 = nums2 - nums1
        fig_venn_data = go.Figure(go.Bar(
            x=["Common numbers", f"Only in {labels[0]}", f"Only in {labels[1]}"],
            y=[len(common), len(only1), len(only2)],
            marker_color=[PINK_M, PINK, GREEN]
        ))
        fig_venn_data.update_layout(title="Unique vs shared contact numbers",
            plot_bgcolor=WHITE, paper_bgcolor=WHITE, font_family="Inter",
            title_font_family="Playfair Display", title_font_size=15,
            margin=dict(l=20,r=20,t=40,b=20))
        figs["number_overlap"] = fig_venn_data

    return figs


# ── PDF Report ────────────────────────────────────────────────────────────────

def generate_pdf(bill_data, df, figs, meta, alerts):
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
        topMargin=2*cm, bottomMargin=2*cm, leftMargin=2*cm, rightMargin=2*cm)
    styles = getSampleStyleSheet()
    story = []

    title_s  = ParagraphStyle("t",  fontName="Helvetica-Bold",   fontSize=26, textColor=colors.HexColor(PINK_D),   alignment=TA_CENTER, spaceAfter=8,  spaceBefore=0)
    sub_s    = ParagraphStyle("s",  fontName="Helvetica",         fontSize=12, textColor=colors.HexColor(HINT),     alignment=TA_CENTER, spaceAfter=20, spaceBefore=4)
    h2_s     = ParagraphStyle("h2", fontName="Helvetica-Bold",   fontSize=14, textColor=colors.HexColor(PINK_D),   spaceBefore=20, spaceAfter=10)
    h3_s     = ParagraphStyle("h3", fontName="Helvetica-Bold",   fontSize=11, textColor=colors.HexColor(TXT),      spaceBefore=12, spaceAfter=6)
    body_s   = ParagraphStyle("b",  fontName="Helvetica",         fontSize=9,  textColor=colors.HexColor(TXT),      leading=14, spaceAfter=4)
    small_s  = ParagraphStyle("sm", fontName="Helvetica",         fontSize=7,  textColor=colors.HexColor(HINT),     alignment=TA_CENTER, spaceAfter=8)
    ai_s     = ParagraphStyle("ai", fontName="Helvetica-Oblique", fontSize=8,  textColor=colors.HexColor("#3E6E38"),
                               backColor=colors.HexColor(GREEN_L), borderPadding=8, spaceAfter=16, spaceBefore=8, alignment=TA_CENTER)
    alert_r_s = ParagraphStyle("ar", fontName="Helvetica",        fontSize=9,  textColor=colors.HexColor(ALERT_RT),
                                backColor=colors.HexColor(ALERT_R), borderPadding=6, spaceAfter=6)
    alert_y_s = ParagraphStyle("ay", fontName="Helvetica",        fontSize=9,  textColor=colors.HexColor(ALERT_YT),
                                backColor=colors.HexColor("#FAEEDA"), borderPadding=6, spaceAfter=6)
    alert_g_s = ParagraphStyle("ag", fontName="Helvetica",        fontSize=9,  textColor=colors.HexColor(ALERT_GT),
                                backColor=colors.HexColor(ALERT_G), borderPadding=6, spaceAfter=6)

    story.append(Paragraph("Peek-a-Bill", title_s))
    story.append(Paragraph("Phone Bill Analysis Report", sub_s))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor(BORDER)))
    story.append(Spacer(1, 12))

    # Telecom + date subtitle
    telecom_name = meta.get("telecom") or bill_data.get("account_info",{}).get("telecom_provider","—")
    bill_date_str = meta.get("bill_date","—")
    story.append(Paragraph(
        f"Telecom Provider: {telecom_name}   ·   Bill Date: {bill_date_str}   ·   Monthly Statement",
        ParagraphStyle("meta_line", fontName="Helvetica", fontSize=9, textColor=colors.HexColor(MUTED),
                       alignment=TA_CENTER, spaceAfter=6)
    ))
    story.append(Paragraph(f"Generated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}", small_s))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "AI Acknowledgment: This report was generated with AI-assisted extraction. "
        "All data was parsed from the uploaded PDF. Please verify against your original bill.", ai_s))

    # Account details table
    story.append(Paragraph("Account & Statement Details", h2_s))
    bi = bill_data.get("billing_info", {})
    si = bill_data.get("statement_info", {})
    ai2 = bill_data.get("account_info", {})
    rows = [
        ["Field","Value"],
        ["Telecom provider", meta.get("telecom","—")],
        ["Phone number", meta.get("phone") or ai2.get("phone_number","—")],
        ["Address", (meta.get("address") or ai2.get("address","—"))[:80]],
        ["Statement number", meta.get("stmt_num") or si.get("statement_number","—")],
        ["Bill date", meta.get("bill_date") or si.get("bill_date","—")],
        ["Previous balance", "₹" + (meta.get("prev_balance") or bi.get("previous_balance","—"))],
        ["Amount payable", "₹" + (meta.get("amount_payable") or bi.get("amount_payable","—"))],
        ["Plan", meta.get("plan_name","—")],
    ]
    tbl = Table(rows, colWidths=[5.5*cm,10.5*cm])
    tbl.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),colors.HexColor(PINK_L)),
        ("TEXTCOLOR",(0,0),(-1,0),colors.HexColor(PINK_D)),
        ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
        ("FONTSIZE",(0,0),(-1,-1),9),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,colors.HexColor(PINK_L)]),
        ("GRID",(0,0),(-1,-1),0.5,colors.HexColor(BORDER)),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("PADDING",(0,0),(-1,-1),6),
    ]))
    story.append(tbl)
    story.append(Spacer(1,14))

    # Device info
    dev = bill_data.get("device_info", {})
    if dev:
        story.append(Paragraph("Device Information", h2_s))
        dev_rows = [["Field","Value"]]
        for k,v in dev.items():
            dev_rows.append([k.upper(), str(v)])
        tbl_d = Table(dev_rows, colWidths=[5.5*cm,10.5*cm])
        tbl_d.setStyle(TableStyle([
            ("BACKGROUND",(0,0),(-1,0),colors.HexColor(GREEN_L)),
            ("TEXTCOLOR",(0,0),(-1,0),colors.HexColor("#3E6E38")),
            ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
            ("FONTSIZE",(0,0),(-1,-1),9),
            ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,colors.HexColor(GREEN_L)]),
            ("GRID",(0,0),(-1,-1),0.5,colors.HexColor("#C0DD97")),
            ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
            ("PADDING",(0,0),(-1,-1),6),
        ]))
        story.append(tbl_d)
        story.append(Spacer(1,14))

    # Suspicious alerts
    if alerts:
        story.append(Paragraph("Suspicious Activity Flags", h2_s))
        for a in alerts:
            style = alert_r_s if a["level"]=="red" else (alert_y_s if a["level"]=="yellow" else alert_g_s)
            story.append(Paragraph(f"{a['icon']}  {a['title']}  —  {a['detail']}", style))
        story.append(Spacer(1,10))

    # Call analytics
    if df is not None and len(df) > 0:
        story.append(Paragraph("Call Analytics", h2_s))
        total_calls = len(df)
        total_secs = df["talk_time_seconds"].sum() if "talk_time_seconds" in df.columns else 0
        top_num = "—"
        if "called_number" in df.columns:
            top_num = df["called_number"].value_counts().index[0] if len(df) > 0 else "—"
        sum_rows = [
            ["Metric","Value"],
            ["Total calls", str(total_calls)],
            ["Total talk time", f"{round(total_secs/3600,1)} hours"],
            ["Most called number", top_num],
            ["Avg call duration", f"{round(total_secs/total_calls/60,1)} min" if total_calls else "—"],
        ]
        tbl2 = Table(sum_rows, colWidths=[8*cm,8*cm])
        tbl2.setStyle(TableStyle([
            ("BACKGROUND",(0,0),(-1,0),colors.HexColor(PINK_L)),
            ("TEXTCOLOR",(0,0),(-1,0),colors.HexColor(PINK_D)),
            ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
            ("FONTSIZE",(0,0),(-1,-1),9),
            ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,colors.HexColor(PINK_L)]),
            ("GRID",(0,0),(-1,-1),0.5,colors.HexColor(BORDER)),
            ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
            ("PADDING",(0,0),(-1,-1),6),
        ]))
        story.append(tbl2)
        story.append(Spacer(1,12))

        # Daily usage chart if date info available
        try:
            df_chart = df.copy()
            df_chart["parsed_date"] = pd.to_datetime(df_chart["call_date"], dayfirst=True, errors="coerce")
            daily_calls = df_chart.groupby(df_chart["parsed_date"].dt.date).size().reset_index()
            daily_calls.columns = ["Date", "Calls"]
            if len(daily_calls) > 1:
                fig_daily = px.bar(daily_calls, x="Date", y="Calls",
                    color_discrete_sequence=[PINK], title="Daily call activity (monthly view)")
                fig_daily.update_layout(
                    plot_bgcolor=WHITE, paper_bgcolor=WHITE, font_family="Inter",
                    font_size=11, title_font_size=13,
                    xaxis=dict(title="Date", tickangle=-45, tickfont=dict(size=9), gridcolor=BORDER),
                    yaxis=dict(title="Number of Calls", tickfont=dict(size=9), gridcolor=BORDER),
                    margin=dict(l=60, r=20, t=50, b=80)
                )
                img_bytes = fig_daily.to_image(format="png", width=700, height=350, scale=1.5)
                story.append(Paragraph("Daily Call Activity", h3_s))
                story.append(RLImage(io.BytesIO(img_bytes), width=16*cm, height=8*cm))
                story.append(Spacer(1, 10))
        except: pass

        for key, fig in figs.items():
            try:
                # Improve axis readability before rendering
                fig.update_layout(
                    font_size=11,
                    xaxis=dict(tickangle=-35, tickfont=dict(size=9), title_font=dict(size=10)),
                    yaxis=dict(tickfont=dict(size=9), title_font=dict(size=10)),
                    margin=dict(l=60, r=20, t=50, b=70)
                )
                img_bytes = fig.to_image(format="png", width=700, height=350, scale=1.5)
                story.append(RLImage(io.BytesIO(img_bytes), width=16*cm, height=8*cm))
                story.append(Spacer(1,10))
            except: pass

    # MCC/MNC
    if meta.get("mcc"):
        story.append(Paragraph("Network & Location", h2_s))
        loc_rows = [
            ["Parameter","Value"],
            ["MCC", meta.get("mcc","—")],
            ["MNC", meta.get("mnc","—")],
            ["Cell ID", meta.get("cell_id","Not provided")],
            ["LAC", meta.get("lac","Not provided")],
            ["Approx location", meta.get("approx_location","—")],
        ]
        tbl3 = Table(loc_rows, colWidths=[8*cm,8*cm])
        tbl3.setStyle(TableStyle([
            ("BACKGROUND",(0,0),(-1,0),colors.HexColor(GREEN_L)),
            ("TEXTCOLOR",(0,0),(-1,0),colors.HexColor("#3E6E38")),
            ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
            ("FONTSIZE",(0,0),(-1,-1),9),
            ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,colors.HexColor(GREEN_L)]),
            ("GRID",(0,0),(-1,-1),0.5,colors.HexColor("#C0DD97")),
            ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
            ("PADDING",(0,0),(-1,-1),6),
        ]))
        story.append(tbl3)

    story.append(Spacer(1,20))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor(BORDER)))
    story.append(Spacer(1,8))
    story.append(Paragraph(
        "Peek-a-Bill · AI-assisted phone bill analysis · Claude by Anthropic · "
        "For informational purposes only. Verify all data against original bill.",
        ParagraphStyle("ft", fontName="Helvetica", fontSize=7, textColor=colors.HexColor(HINT), alignment=TA_CENTER)
    ))
    doc.build(story)
    buf.seek(0)
    return buf


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown('<p class="brand-name">Peek-a-Bill</p>', unsafe_allow_html=True)
    st.markdown('<p class="brand-tagline">your calls, caught red-handed 🔍</p>', unsafe_allow_html=True)
    st.markdown("---")

    pages = {
        "upload":   ("📄", "Upload bill"),
        "dashboard":("📊", "Dashboard"),
        "calls":    ("📞", "Call insights"),
        "alerts":   ("🚨", "Suspicious alerts"),
        "data":     ("📡", "Data usage"),
        "location": ("🗺", "Location (MCC/MNC)"),
        "billing":  ("💳", "Billing summary"),
        "device":   ("📱", "Device info"),
        "compare":  ("⚖",  "Compare bills"),
        "report":   ("📥", "Generate report"),
    }

    st.markdown('<p class="section-header">Upload</p>', unsafe_allow_html=True)
    for pid in ["upload"]:
        icon, label = pages[pid]
        if st.button(f"{icon}  {label}", key=f"nav_{pid}", use_container_width=True):
            st.session_state.page = pid

    st.markdown('<p class="section-header">Analysis</p>', unsafe_allow_html=True)
    for pid in ["dashboard","calls","alerts","data","location","billing","device"]:
        icon, label = pages[pid]
        if st.button(f"{icon}  {label}", key=f"nav_{pid}", use_container_width=True):
            st.session_state.page = pid

    st.markdown('<p class="section-header">More</p>', unsafe_allow_html=True)
    for pid in ["compare","report"]:
        icon, label = pages[pid]
        if st.button(f"{icon}  {label}", key=f"nav_{pid}", use_container_width=True):
            st.session_state.page = pid

    st.markdown("""
    <div class="ai-badge">
        ✦ AI-assisted extraction<br>
        <span style="font-weight:400">Claude by Anthropic</span>
    </div>
    """, unsafe_allow_html=True)


# ── Pages ─────────────────────────────────────────────────────────────────────
page = st.session_state.page

# ════════════════════ UPLOAD ═════════════════════════
if page == "upload":
    st.markdown('<p class="page-title">Upload your phone bill</p>', unsafe_allow_html=True)
    st.markdown('<p class="page-sub">Drop your PDF and we\'ll handle the rest — beautifully.</p>', unsafe_allow_html=True)
    st.markdown("---")

    col1, col2 = st.columns([1.4, 1])
    with col1:
        uploaded = st.file_uploader("Your PDF bill", type=["pdf"],
            help="Supports Airtel, Jio, Vodafone/Vi, BSNL")
        if uploaded:
            st.success(f"✓  {uploaded.name} received")
            with st.spinner("Reading your bill..."):
                bd = extract_bill_data(uploaded)
                st.session_state.bill_data = bd
            if bd["call_records"]:
                st.session_state.df_calls = pd.DataFrame(bd["call_records"])
                st.info(f"Found {len(bd['call_records'])} call records.")
            else:
                st.warning("No call records auto-detected. Add them manually below.")
                with st.expander("🔍 Debug: view raw extracted text (first 2000 chars)"):
                    st.text(bd.get("raw_text","")[:2000])
            if bd.get("data_session_records"):
                st.session_state["df_data_sessions"] = pd.DataFrame(bd["data_session_records"])
                st.info(f"Found {len(bd['data_session_records'])} data session records.")
            if bd["device_info"]:
                st.info(f"Device info found: {', '.join(bd['device_info'].keys())}")

    with col2:
        st.markdown("#### Bill details")
        st.caption("Auto-filled where possible — correct as needed.")
        bd = st.session_state.bill_data or {}
        ai2 = bd.get("account_info", {})
        bi = bd.get("billing_info", {})
        si = bd.get("statement_info", {})

        telecom   = st.selectbox("Telecom provider", ["Airtel","Jio","Vodafone/Vi","BSNL","Other"],
                        index=["Airtel","Jio","Vodafone/Vi","BSNL","Other"].index(
                            ai2.get("telecom_provider","Airtel")
                        ) if ai2.get("telecom_provider") in ["Airtel","Jio","Vodafone/Vi","BSNL","Other"] else 0)
        phone     = st.text_input("Phone number", value=ai2.get("phone_number",""))
        address   = st.text_area("Billing address", value=ai2.get("address",""), height=60)
        stmt_num  = st.text_input("Statement number", value=si.get("statement_number",""))
        bill_date = st.text_input("Bill date", value=si.get("bill_date",""))
        c1, c2 = st.columns(2)
        prev_bal = c1.text_input("Previous balance ₹", value=bi.get("previous_balance",""))
        amt_pay  = c2.text_input("Amount payable ₹",   value=bi.get("amount_payable",""))
        plan_nm  = st.text_input("Plan / tariff name",  value=bd.get("plan_details",{}).get("plan_name",""))

        if st.button("Save & continue →"):
            st.session_state.meta = {
                "telecom": telecom, "phone": phone, "address": address,
                "stmt_num": stmt_num, "bill_date": bill_date,
                "prev_balance": prev_bal, "amount_payable": amt_pay, "plan_name": plan_nm,
            }
            st.success("Saved! Head to Dashboard or Call Insights.")

    st.markdown("---")
    st.markdown("#### Manual call records")
    st.caption("Format per line: `date, start_time, end_time, number, seconds`")
    manual = st.text_area("Paste call log", height=100,
        placeholder="01/09/2024, 09:30:00, 09:35:22, 9876543210, 322")
    if st.button("Parse & add"):
        recs = parse_manual_calls(manual)
        if recs:
            df_new = pd.DataFrame(recs)
            existing = st.session_state.df_calls
            st.session_state.df_calls = pd.concat([existing, df_new], ignore_index=True) if existing is not None else df_new
            st.success(f"Added {len(recs)} records.")
        else:
            st.error("Could not parse. Check format.")

    st.markdown("#### Manual SMS records")
    st.caption("Format: `date, time, number`")
    sms_manual = st.text_area("Paste SMS log", height=80, placeholder="01/09/2024, 22:30:00, 9876543210")
    if st.button("Parse SMS"):
        sms_rows = []
        for line in sms_manual.strip().split("\n"):
            parts = re.split(r'[,\t|]+', line.strip())
            if len(parts) >= 3:
                sms_rows.append({"date": parts[0].strip(), "time": parts[1].strip(), "number": parts[2].strip()})
        if sms_rows:
            bd2 = st.session_state.bill_data or {}
            bd2["sms_records"] = sms_rows
            st.session_state.bill_data = bd2
            st.success(f"Added {len(sms_rows)} SMS records.")

# ════════════════════ DASHBOARD ══════════════════════
elif page == "dashboard":
    meta = st.session_state.meta
    bd = st.session_state.bill_data or {}
    bi = bd.get("billing_info", {})
    df = st.session_state.df_calls

    st.markdown('<p class="page-title">Dashboard overview</p>', unsafe_allow_html=True)
    st.markdown(f'<p class="page-sub">{meta.get("telecom","—")} · Statement {meta.get("stmt_num","—")} · {meta.get("bill_date","—")}</p>', unsafe_allow_html=True)
    st.markdown("---")

    total_calls = len(df) if df is not None else 0
    total_secs  = df["talk_time_seconds"].sum() if df is not None and "talk_time_seconds" in df.columns else 0
    amt = meta.get("amount_payable") or bi.get("amount_payable","—")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Amount Payable", f"₹{amt}")
    c2.metric("Total Calls", str(total_calls))
    c3.metric("Talk Time", f"{round(total_secs/3600,1)}h")
    c4.metric("Phone", meta.get("phone","—"))

    # Quick alert banner
    if df is not None and len(df) > 0:
        alerts = detect_suspicious(df, pd.DataFrame(bd.get("sms_records",[])) if bd.get("sms_records") else None)
        red_alerts = [a for a in alerts if a["level"]=="red"]
        if red_alerts:
            st.markdown(f'<div class="alert-red">🚨 <strong>{len(red_alerts)} suspicious flag(s)</strong> detected — go to Suspicious Alerts for details.</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="alert-green">✓ No suspicious activity detected in this bill.</div>', unsafe_allow_html=True)

    st.markdown("---")
    if df is not None and len(df) > 0:
        figs = build_charts(df)
        keys = list(figs.keys())
        col1, col2 = st.columns(2)
        for i, k in enumerate(keys):
            (col1 if i % 2 == 0 else col2).plotly_chart(figs[k], use_container_width=True)
    else:
        st.info("Upload a bill and add call records to see charts.")

# ════════════════════ CALL INSIGHTS ══════════════════
elif page == "calls":
    st.markdown('<p class="page-title">Call insights</p>', unsafe_allow_html=True)
    st.markdown("---")
    df = st.session_state.df_calls

    if df is not None and len(df) > 0:
        figs = build_charts(df)
        for k, fig in figs.items():
            st.plotly_chart(fig, use_container_width=True)

        st.markdown("#### Full call log")
        st.dataframe(df, use_container_width=True)
        st.download_button("⬇ Download call log (CSV)", df.to_csv(index=False).encode(),
            "peekabill_calls.csv", "text/csv")
    else:
        st.info("No call records yet. Upload a bill or add records manually on the Upload page.")

# ════════════════════ SUSPICIOUS ALERTS ══════════════
elif page == "alerts":
    st.markdown('<p class="page-title">Suspicious activity flags</p>', unsafe_allow_html=True)
    st.markdown('<p class="page-sub">We scan for late-night calls, frequent unknowns, high SMS volume, and more.</p>', unsafe_allow_html=True)
    st.markdown("---")

    df = st.session_state.df_calls
    bd = st.session_state.bill_data or {}
    sms_df = pd.DataFrame(bd.get("sms_records",[])) if bd.get("sms_records") else None

    if df is not None and len(df) > 0:
        alerts = detect_suspicious(df, sms_df)

        red   = [a for a in alerts if a["level"]=="red"]
        yell  = [a for a in alerts if a["level"]=="yellow"]
        green = [a for a in alerts if a["level"]=="green"]

        c1, c2, c3 = st.columns(3)
        c1.metric("🔴 Critical flags", len(red))
        c2.metric("🟡 Warnings",       len(yell))
        c3.metric("🟢 Checks passed",  1 if green else 0)
        st.markdown("---")

        if red:
            st.markdown("#### Critical flags")
            for a in red:
                st.markdown(f'<div class="alert-red"><strong>{a["icon"]} {a["title"]}</strong><br>{a["detail"]}</div>', unsafe_allow_html=True)

        if yell:
            st.markdown("#### Warnings")
            for a in yell:
                st.markdown(f'<div class="alert-yellow"><strong>{a["icon"]} {a["title"]}</strong><br>{a["detail"]}</div>', unsafe_allow_html=True)

        if green:
            for a in green:
                st.markdown(f'<div class="alert-green"><strong>{a["icon"]} {a["title"]}</strong><br>{a["detail"]}</div>', unsafe_allow_html=True)

        # Late-night timeline chart
        try:
            df2 = df.copy()
            df2["hour"] = pd.to_datetime(df2["start_time"], format="%H:%M:%S", errors="coerce").dt.hour
            if df2["hour"].isna().all():
                df2["hour"] = pd.to_datetime(df2["start_time"], format="%H:%M", errors="coerce").dt.hour
            if df2["hour"].notna().any():
                st.markdown("---")
                st.markdown("#### Call activity by hour — late-night zone highlighted")
                hc = df2.groupby("hour").size().reset_index()
                hc.columns = ["Hour","Calls"]
                hc["color"] = hc["Hour"].apply(lambda h: "Late night (11PM–5AM)" if (h >= 23 or h <= 5) else "Normal hours")
                fig_h = px.bar(hc, x="Hour", y="Calls", color="color",
                    color_discrete_map={"Late night (11PM–5AM)": ALERT_RT, "Normal hours": PINK},
                    title="Hourly call distribution")
                fig_h.update_layout(plot_bgcolor=WHITE, paper_bgcolor=WHITE,
                    font_family="Inter", title_font_family="Playfair Display",
                    margin=dict(l=20,r=20,t=40,b=20))
                st.plotly_chart(fig_h, use_container_width=True)
        except: pass

        # Export alerts CSV
        alerts_df = pd.DataFrame([{
            "Level": a["level"], "Flag": a["title"], "Detail": a["detail"], "Count": a["count"]
        } for a in alerts])
        st.download_button("⬇ Download alerts report (CSV)",
            alerts_df.to_csv(index=False).encode(), "peekabill_alerts.csv", "text/csv")
    else:
        st.info("Upload a bill with call records to run suspicious activity checks.")

# ════════════════════ DATA USAGE ══════════════════════
elif page == "data":
    st.markdown('<p class="page-title">Data usage</p>', unsafe_allow_html=True)
    st.markdown("---")

    df_ds = st.session_state.get("df_data_sessions")

    if df_ds is not None and len(df_ds) > 0:
        st.markdown('<div class="alert-green">✓ Data sessions auto-detected from your bill.</div>', unsafe_allow_html=True)
        st.markdown("")

        total_sessions  = len(df_ds)
        total_mb        = df_ds["total_mb"].sum()
        charged_mb      = df_ds["charged_mb"].sum()

        c1, c2, c3 = st.columns(3)
        c1.metric("Total sessions",    str(total_sessions))
        c2.metric("Total usage",       f"{round(total_mb/1024, 2)} GB" if total_mb >= 1024 else f"{round(total_mb, 1)} MB")
        c3.metric("Chargeable usage",  f"{round(charged_mb/1024, 2)} GB" if charged_mb >= 1024 else f"{round(charged_mb, 1)} MB")

        st.markdown("---")

        # Daily usage chart
        try:
            df_ds["parsed_date"] = pd.to_datetime(df_ds["start_date"], dayfirst=True, errors="coerce")
            daily = df_ds.groupby("parsed_date")["total_mb"].sum().reset_index()
            daily.columns = ["Date", "Usage (MB)"]
            fig_daily = px.bar(daily, x="Date", y="Usage (MB)",
                color_discrete_sequence=[GREEN], title="Daily data usage (MB)")
            fig_daily.update_layout(plot_bgcolor=WHITE, paper_bgcolor=WHITE, font_family="Inter",
                title_font_family="Playfair Display", title_font_size=15,
                xaxis=dict(gridcolor=BORDER), yaxis=dict(gridcolor=BORDER),
                margin=dict(l=20,r=20,t=40,b=20))
            st.plotly_chart(fig_daily, use_container_width=True)
        except: pass

        col1, col2 = st.columns(2)

        # Top destinations
        with col1:
            try:
                dest = df_ds.groupby("destination")["total_mb"].sum().sort_values(ascending=False).head(8).reset_index()
                dest.columns = ["Destination", "Usage (MB)"]
                fig_dest = px.bar(dest, x="Usage (MB)", y="Destination", orientation="h",
                    color_discrete_sequence=[PINK], title="Top destinations by usage")
                fig_dest.update_layout(plot_bgcolor=WHITE, paper_bgcolor=WHITE, font_family="Inter",
                    title_font_family="Playfair Display", title_font_size=15,
                    margin=dict(l=20,r=20,t=40,b=20))
                st.plotly_chart(fig_dest, use_container_width=True)
            except: pass

        # Usage by hour
        with col2:
            try:
                df_ds["hour"] = pd.to_datetime(df_ds["start_time"], format="%H:%M:%S", errors="coerce").dt.hour
                hourly = df_ds.groupby("hour")["total_mb"].sum().reset_index()
                hourly.columns = ["Hour", "Usage (MB)"]
                fig_hour = px.bar(hourly, x="Hour", y="Usage (MB)",
                    color_discrete_sequence=[PINK_M], title="Data usage by hour of day")
                fig_hour.update_layout(plot_bgcolor=WHITE, paper_bgcolor=WHITE, font_family="Inter",
                    title_font_family="Playfair Display", title_font_size=15,
                    margin=dict(l=20,r=20,t=40,b=20))
                st.plotly_chart(fig_hour, use_container_width=True)
            except: pass

        # Session duration vs usage scatter
        try:
            df_ds["start_dt"] = pd.to_datetime(df_ds["start_date"] + " " + df_ds["start_time"], dayfirst=True, errors="coerce")
            df_ds["end_dt"]   = pd.to_datetime(df_ds["end_date"]   + " " + df_ds["end_time"],   dayfirst=True, errors="coerce")
            df_ds["duration_min"] = (df_ds["end_dt"] - df_ds["start_dt"]).dt.total_seconds() / 60
            valid = df_ds[df_ds["duration_min"] > 0]
            if len(valid) > 1:
                fig_scatter = px.scatter(valid, x="duration_min", y="total_mb",
                    color="destination", title="Session duration vs usage",
                    labels={"duration_min": "Duration (min)", "total_mb": "Usage (MB)"},
                    color_discrete_sequence=px.colors.qualitative.Pastel)
                fig_scatter.update_layout(plot_bgcolor=WHITE, paper_bgcolor=WHITE, font_family="Inter",
                    title_font_family="Playfair Display", title_font_size=15,
                    margin=dict(l=20,r=20,t=40,b=20))
                st.plotly_chart(fig_scatter, use_container_width=True)
        except: pass

        st.markdown("#### Session log")
        st.dataframe(df_ds.drop(columns=["parsed_date","start_dt","end_dt","duration_min","hour"], errors="ignore"),
            use_container_width=True)
        st.download_button("⬇ Download session log (CSV)",
            df_ds.to_csv(index=False).encode(), "peekabill_data_sessions.csv", "text/csv")

    else:
        st.info("No data sessions auto-detected. You can enter weekly usage manually below.")
        st.markdown("#### Weekly data breakdown (GB)")
        weeks, vals = [], []
        cols = st.columns(4)
        for i in range(4):
            v = cols[i].number_input(f"Week {i+1}", min_value=0.0, step=0.1, key=f"wk{i}")
            weeks.append(f"Week {i+1}")
            vals.append(v)

        if any(v > 0 for v in vals):
            wdf = pd.DataFrame({"Week": weeks, "Data (GB)": vals})
            fig = px.bar(wdf, x="Week", y="Data (GB)", color_discrete_sequence=[GREEN],
                title="Weekly data usage")
            fig.update_layout(plot_bgcolor=WHITE, paper_bgcolor=WHITE, font_family="Inter",
                title_font_family="Playfair Display", title_font_size=15,
                xaxis=dict(gridcolor=BORDER), yaxis=dict(gridcolor=BORDER),
                margin=dict(l=20,r=20,t=40,b=20))
            st.plotly_chart(fig, use_container_width=True)
            total = sum(vals)
            st.metric("Total data this period", f"{round(total,2)} GB")
            st.metric("Daily average", f"{round(total/28,2)} GB")

# ════════════════════ LOCATION ════════════════════════
elif page == "location":
    st.markdown('<p class="page-title">Network triangulation</p>', unsafe_allow_html=True)
    st.markdown('<p class="page-sub">Enter MCC/MNC and Cell ID to see your approximate network location.</p>', unsafe_allow_html=True)
    st.markdown("---")

    meta = st.session_state.meta
    telecom = meta.get("telecom","Airtel")
    known = TELECOM_MCC_MNC.get(telecom, [])

    col1, col2 = st.columns([1, 1.3])
    with col1:
        mcc_def = known[0][0] if known else ""
        mnc_def = known[0][1] if known else ""
        if known:
            st.markdown(f'<div class="green-pill">Auto-detected: {telecom} → MCC {mcc_def}, MNC {mnc_def}</div>', unsafe_allow_html=True)
            st.caption("")
        mcc     = st.text_input("MCC", value=mcc_def, placeholder="404")
        mnc     = st.text_input("MNC", value=mnc_def, placeholder="10")
        cell_id = st.text_input("Cell ID (optional)", placeholder="From bill / Android settings")
        lac     = st.text_input("LAC (optional)", placeholder="Location area code")

        if st.button("Locate on map"):
            lat, lon, city = get_location(mcc, mnc, cell_id, lac)
            st.session_state.meta.update({"mcc":mcc,"mnc":mnc,"cell_id":cell_id,"lac":lac,
                "approx_lat":lat,"approx_lon":lon,"approx_location":city or "India"})

        st.markdown("---")
        st.caption("**Where to find Cell ID / LAC:**\n- Android: Settings → About Phone → Status\n- Apps: Network Cell Info, OpenSignal\n- BSNL/Airtel detailed CDR may include tower data")

        if known:
            st.markdown(f"#### Known codes for {telecom}")
            st.dataframe(pd.DataFrame(known, columns=["MCC","MNC"]), hide_index=True, use_container_width=True)

    with col2:
        lat = st.session_state.meta.get("approx_lat")
        lon = st.session_state.meta.get("approx_lon")
        city = st.session_state.meta.get("approx_location","")
        if lat and lon:
            fig_map = go.Figure(go.Scattermapbox(
                lat=[lat], lon=[lon], mode="markers",
                marker=go.scattermapbox.Marker(size=16, color=PINK),
                text=[f"{telecom} · {city}"]
            ))
            fig_map.update_layout(
                mapbox_style="open-street-map",
                mapbox=dict(center=dict(lat=lat,lon=lon), zoom=8),
                margin=dict(l=0,r=0,t=0,b=0), height=440
            )
            st.plotly_chart(fig_map, use_container_width=True)
            st.caption(f"Approximate: {city} ({round(lat,4)}, {round(lon,4)}). Based on MCC/MNC only — not GPS-precise.")
        else:
            st.markdown(f"""
            <div style="background:{GREEN_BG};border:1px solid {GREEN_L};border-radius:12px;
                padding:40px 20px;text-align:center;color:#3E6E38;height:440px;
                display:flex;align-items:center;justify-content:center;flex-direction:column;">
                <svg width="40" height="40" viewBox="0 0 40 40" fill="none" stroke="#6A9E62" stroke-width="2">
                    <circle cx="20" cy="16" r="8"/><path d="M20 40C20 40 6 26 6 18a14 14 0 0 1 28 0C34 26 20 40 20 40z"/>
                </svg>
                <p style="margin-top:14px;font-size:13px;font-weight:600;">Enter MCC/MNC and click Locate</p>
            </div>""", unsafe_allow_html=True)

# ════════════════════ BILLING ═════════════════════════
elif page == "billing":
    st.markdown('<p class="page-title">Billing summary</p>', unsafe_allow_html=True)
    st.markdown("---")
    meta = st.session_state.meta
    bd = st.session_state.bill_data or {}

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### Account details")
        for label, val in [
            ("Telecom", meta.get("telecom","—")),
            ("Phone", meta.get("phone","—")),
            ("Plan", meta.get("plan_name","—")),
            ("Bill date", meta.get("bill_date","—")),
            ("Statement #", meta.get("stmt_num","—")),
        ]:
            st.markdown(f"**{label}:** {val}")
    with col2:
        c1, c2 = st.columns(2)
        c1.metric("Previous Balance", f"₹{meta.get('prev_balance','—')}")
        c2.metric("Amount Payable",   f"₹{meta.get('amount_payable','—')}")

    st.markdown("---")
    st.markdown(f"**Billing address:** {meta.get('address','Not provided')}")

    if bd.get("raw_text"):
        with st.expander("View raw extracted text"):
            st.text(bd["raw_text"][:3000])

# ════════════════════ DEVICE INFO ════════════════════
elif page == "device":
    st.markdown('<p class="page-title">Device information</p>', unsafe_allow_html=True)
    st.markdown('<p class="page-sub">Extracted from bill PDF or enter manually below.</p>', unsafe_allow_html=True)
    st.markdown("---")

    bd = st.session_state.bill_data or {}
    dev = bd.get("device_info", {})

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### Auto-extracted device info")
        if dev:
            for k, v in dev.items():
                st.markdown(f"""
                <div class="device-card">
                    <div class="device-label">{k.upper()}</div>
                    <div class="device-val">{v}</div>
                </div>""", unsafe_allow_html=True)
        else:
            st.info("No device info auto-detected in this bill PDF.")

    with col2:
        st.markdown("#### Enter device info manually")
        st.caption("Some operators print this on the bill. You can also check your phone settings.")
        imei   = st.text_input("IMEI number (15 digits)", placeholder="352099001761481")
        model  = st.text_input("Device model", placeholder="Samsung Galaxy S23")
        imsi   = st.text_input("IMSI (from SIM, optional)", placeholder="404101234567890")
        os_ver = st.text_input("OS / Android version (optional)", placeholder="Android 14")
        sim_sl = st.selectbox("SIM slot used", ["SIM 1","SIM 2","Unknown"])
        icc    = st.text_input("ICCID (SIM serial, optional)", placeholder="8991101200003204510")

        if st.button("Save device info"):
            dev_updated = {
                "imei": imei, "model": model, "imsi": imsi,
                "os": os_ver, "sim_slot": sim_sl, "iccid": icc
            }
            dev_updated = {k: v for k, v in dev_updated.items() if v}
            bd["device_info"] = dev_updated
            st.session_state.bill_data = bd
            st.success("Device info saved.")

    st.markdown("---")
    st.markdown("#### IMEI lookup")
    st.caption("IMEI reveals manufacturer and device model. First 8 digits = TAC (Type Allocation Code).")
    imei_check = st.text_input("Enter IMEI to decode", placeholder="352099001761481")
    if st.button("Decode IMEI") and len(imei_check) >= 8:
        tac = imei_check[:8]
        # Validate Luhn
        def luhn(n):
            s, odd = 0, True
            for d in reversed(n):
                d = int(d)
                if not odd: d = d*2 if d<5 else d*2-9
                s += d; odd = not odd
            return s % 10 == 0
        valid = luhn(imei_check) if len(imei_check)==15 else None
        col_a, col_b = st.columns(2)
        col_a.markdown(f"""
        <div class="device-card">
            <div class="device-label">TAC (Type Allocation Code)</div>
            <div class="device-val">{tac}</div>
            <div style="font-size:10px;color:{MUTED};margin-top:3px;">First 8 digits identify the device model</div>
        </div>""", unsafe_allow_html=True)
        col_b.markdown(f"""
        <div class="device-card">
            <div class="device-label">Luhn check</div>
            <div class="device-val" style="color:{'#3E6E38' if valid else '#A32D2D'}">
                {"✓ Valid IMEI" if valid else ("✗ Invalid" if valid is False else "Enter 15 digits")}
            </div>
        </div>""", unsafe_allow_html=True)
        st.caption("For full model lookup, use imei.info or similar public databases.")

# ════════════════════ COMPARE ════════════════════════
elif page == "compare":
    st.markdown('<p class="page-title">Compare two bills</p>', unsafe_allow_html=True)
    st.markdown('<p class="page-sub">Upload a second bill to compare call patterns, costs, and activity side by side.</p>', unsafe_allow_html=True)
    st.markdown("---")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f'<div class="info-pill">Bill 1</div>', unsafe_allow_html=True)
        st.markdown("")
        bd1  = st.session_state.bill_data
        df1  = st.session_state.df_calls
        meta1 = st.session_state.meta
        if bd1:
            st.success(f"✓ Bill 1 loaded — {meta1.get('telecom','—')} · {meta1.get('bill_date','—')}")
            st.metric("Amount payable", f"₹{meta1.get('amount_payable','—')}")
            st.metric("Calls", str(len(df1)) if df1 is not None else "0")
        else:
            st.info("Upload Bill 1 on the Upload page first.")

    with col2:
        st.markdown(f'<div class="green-pill">Bill 2</div>', unsafe_allow_html=True)
        st.markdown("")
        uploaded2 = st.file_uploader("Upload second bill PDF", type=["pdf"], key="bill2_upload")
        if uploaded2:
            with st.spinner("Reading bill 2..."):
                bd2 = extract_bill_data(uploaded2)
                st.session_state.bill_data_2 = bd2
                if bd2["call_records"]:
                    st.session_state.df_calls_2 = pd.DataFrame(bd2["call_records"])

        if st.session_state.bill_data_2:
            st.success("✓ Bill 2 loaded")
            t2  = st.text_input("Telecom (bill 2)", placeholder="Jio")
            bd2_date = st.text_input("Bill date (bill 2)", placeholder="01/10/2024")
            amt2 = st.text_input("Amount payable ₹ (bill 2)", placeholder="920")
            if st.button("Save bill 2 details"):
                st.session_state.meta_2 = {"telecom": t2, "bill_date": bd2_date, "amount_payable": amt2}
                st.success("Saved.")

    st.markdown("---")
    df1 = st.session_state.df_calls
    df2 = st.session_state.df_calls_2
    meta1 = st.session_state.meta
    meta2 = st.session_state.meta_2

    if df1 is not None and df2 is not None and len(df1) > 0 and len(df2) > 0:
        st.markdown("### Side-by-side comparison")
        figs_compare = compare_bills(df1, df2, meta1, meta2)

        c1, c2 = st.columns(2)
        keys = list(figs_compare.keys())
        for i, k in enumerate(keys):
            (c1 if i%2==0 else c2).plotly_chart(figs_compare[k], use_container_width=True)

        # Summary table
        st.markdown("#### Summary table")
        label1 = meta1.get("telecom","Bill 1") + " " + meta1.get("bill_date","")
        label2 = meta2.get("telecom","Bill 2") + " " + meta2.get("bill_date","")
        t1_secs = df1["talk_time_seconds"].sum() if "talk_time_seconds" in df1.columns else 0
        t2_secs = df2["talk_time_seconds"].sum() if "talk_time_seconds" in df2.columns else 0
        top1 = df1["called_number"].value_counts().index[0] if "called_number" in df1.columns and len(df1)>0 else "—"
        top2 = df2["called_number"].value_counts().index[0] if "called_number" in df2.columns and len(df2)>0 else "—"

        comp_df = pd.DataFrame({
            "Metric": ["Total calls", "Total talk time", "Most called number",
                        "Unique numbers", "Amount payable"],
            label1: [len(df1), f"{round(t1_secs/3600,1)}h", top1,
                     df1["called_number"].nunique() if "called_number" in df1.columns else "—",
                     f"₹{meta1.get('amount_payable','—')}"],
            label2: [len(df2), f"{round(t2_secs/3600,1)}h", top2,
                     df2["called_number"].nunique() if "called_number" in df2.columns else "—",
                     f"₹{meta2.get('amount_payable','—')}"],
        })
        st.dataframe(comp_df, use_container_width=True, hide_index=True)

        st.download_button("⬇ Download comparison CSV",
            comp_df.to_csv(index=False).encode(), "peekabill_comparison.csv", "text/csv")
    else:
        st.info("Load call records for both bills to see the comparison charts.")

# ════════════════════ REPORT ═════════════════════════
elif page == "report":
    st.markdown('<p class="page-title">Generate report</p>', unsafe_allow_html=True)
    st.markdown('<p class="page-sub">Export your full analysis in multiple formats.</p>', unsafe_allow_html=True)
    st.markdown("---")

    df   = st.session_state.df_calls
    bd   = st.session_state.bill_data or {}
    meta = st.session_state.meta
    figs = build_charts(df) if df is not None and len(df) > 0 else {}
    alerts = detect_suspicious(df, pd.DataFrame(bd.get("sms_records",[])) if bd.get("sms_records") else None) if df is not None and len(df) > 0 else []

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("#### PDF report")
        st.caption("Full report — charts, alerts, device info, AI acknowledgment.")
        if st.button("Build PDF"):
            with st.spinner("Building PDF..."):
                try:
                    pdf_buf = generate_pdf(bd, df, figs, meta, alerts)
                    st.download_button("⬇ Download PDF", pdf_buf,
                        f"peekabill_report_{datetime.now().strftime('%Y%m%d')}.pdf", "application/pdf")
                except Exception as e:
                    st.error(f"PDF error: {e}")

    with col2:
        st.markdown("#### CSV exports")
        st.caption("Structured data files.")
        if df is not None and len(df) > 0:
            st.download_button("⬇ Call records CSV", df.to_csv(index=False).encode(),
                "peekabill_calls.csv", "text/csv")
        summary_rows = [["Field","Value"]] + [[k,v] for k,v in meta.items()]
        buf_s = io.StringIO()
        csv.writer(buf_s).writerows(summary_rows)
        st.download_button("⬇ Bill summary CSV", buf_s.getvalue().encode(),
            "peekabill_summary.csv", "text/csv")
        if alerts:
            alerts_df = pd.DataFrame([{"Level":a["level"],"Flag":a["title"],"Detail":a["detail"]} for a in alerts])
            st.download_button("⬇ Alerts CSV", alerts_df.to_csv(index=False).encode(),
                "peekabill_alerts.csv", "text/csv")

    with col3:
        st.markdown("#### Chart images (PNG)")
        st.caption("Individual chart downloads.")
        for key, fig in figs.items():
            try:
                img_bytes = fig.to_image(format="png", width=800, height=500, scale=2)
                st.download_button(f"⬇ {key.replace('_',' ').title()}",
                    img_bytes, f"peekabill_{key}.png", "image/png")
            except:
                st.caption(f"Install kaleido for PNG: `pip install kaleido`")
                break

    st.markdown("---")
    st.markdown(f"""
    <div class="ai-badge">
        <strong>AI Acknowledgment</strong><br>
        This report was generated with AI-assisted data extraction using <strong>Claude by Anthropic</strong>.
        All information was parsed from the uploaded PDF phone bill using pattern recognition and NLP.
        Peek-a-Bill does not retain your data beyond this browser session.
        Always verify results against your original bill document.
    </div>
    """, unsafe_allow_html=True)

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="footer-note">
    Peek-a-Bill · AI-assisted phone bill analysis · Powered by Claude (Anthropic) · Streamlit<br>
    Your data is processed locally in your session only · Not stored, not shared.
</div>
""", unsafe_allow_html=True)
