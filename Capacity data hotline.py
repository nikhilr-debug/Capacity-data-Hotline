import streamlit as st
import pandas as pd
import requests
import numpy as np

# Set up page configuration for a wide, modern dashboard layout
st.set_page_config(
    page_title="TC Performance & Growth Dashboard",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 1. DATA RETRIEVAL & BULLETPROOF PARSING ---
@st.cache_data(ttl=600)  # Cache data for 10 minutes to protect API limits
def fetch_dashboard_data():
    api_url = "https://redash.vahan.link/api/queries/17597/results.json?api_key=4aFm2iOoyx8I91svQccdeZr0jmaiUsMFSRinZcmu"
    
    try:
        response = requests.get(api_url, timeout=10)
        if response.status_code == 200:
            data = response.json()['query_result']['data']['rows']
            df = pd.DataFrame(data)
            
            # Normalize column names to Title Case if API returns snake_case
            rename_map = {
                'channel': 'Channel', 'week_start': 'Week Start', 'start': 'Week Start',
                'active_tcs': 'Active TCs', 'retained_tcs': 'Retained TCs', 
                'new_tcs': 'New TCs', 'resurrected_tcs': 'Resurrected TCs', 
                'churn': 'Churn', 'net_new_additions': 'Net New Additions',
                'region': 'Region', 'connected_tcs': 'Connected TCs', 'productive_tcs': 'Productive TCs'
            }
            df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
            
            # Robust Date Conversion: Force convert any column containing the word "start"
            for col in df.columns:
                if 'start' in col.lower():
                    df[col] = pd.to_datetime(df[col], errors='coerce')
            return df
            
    except Exception as e:
        st.sidebar.warning("Using local reference data context (API offline or unreachable).")
    
    # Structural Fallback (Extended to 5 weeks to demonstrate requirement)
    dates = pd.date_range(end="2026-06-08", periods=5, freq="W-MON")
    channels = ["DC", "Existing VL", "BPO", "New + WinBack"]
    regions = ["NCR-UP", "Karnataka", "MPCG", "East+West", "West", "Bihar-Orissa"]
    
    channel_mock_values = {
        "DC": [(34, 34, 0, 0, 0), (31, 31, 0, 0, 3), (33, 29, 4, 0, 2), (35, 31, 3, 1, 2), (36, 32, 2, 2, 1)],
        "Existing VL": [(599, 449, 100, 50, 0), (527, 454, 43, 30, 140), (591, 442, 93, 56, 83), (546, 466, 49, 31, 120), (550, 470, 50, 40, 110)],
        "BPO": [(27, 24, 2, 1, 0), (29, 25, 4, 0, 2), (27, 27, 0, 0, 2), (25, 23, 1, 1, 4), (26, 24, 2, 1, 3)],
        "New + WinBack": [(5, 2, 2, 1, 0), (13, 3, 8, 2, 1), (23, 8, 15, 0, 5), (40, 14, 23, 3, 7), (45, 18, 25, 5, 6)]
    }
    
    records = []
    for ch in channels:
        for idx, dt in enumerate(dates):
            vals = channel_mock_values[ch][idx]
            net_new = (vals[2] + vals[3]) - vals[4] if idx > 0 else 0
            records.append({
                "Channel": ch, "Week Start": dt, "Active TCs": vals[0], "Retained TCs": vals[1], 
                "New TCs": vals[2], "Resurrected TCs": vals[3], "Churn": vals[4] if idx > 0 else np.nan,
                "Net New Additions": net_new if idx > 0 else np.nan, "Region": np.random.choice(regions),
                "Connected TCs": int(vals[0] * 0.82), "Productive TCs": int(vals[0] * 0.61)
            })
            
    return pd.DataFrame(records)

df_raw = fetch_dashboard_data()

# Clean up structural missing values if any
for core_col in ['Active TCs', 'Retained TCs', 'New TCs', 'Resurrected TCs', 'Churn', 'Net New Additions']:
    if core_col not in df_raw.columns:
        df_raw[core_col] = np.nan

# --- 2. DYNAMIC LAST 5 WEEKS FILTER ENGINE ---
# Identify the 5 most recent unique week timestamps available in the dataset
last_5_unique_weeks = sorted(df_raw['Week Start'].dropna().unique(), reverse=True)[:5]

# Filter down dataset immediately to only contain those 5 chronological periods
df_5_weeks = df_raw[df_raw['Week Start'].isin(last_5_unique_weeks)].copy()

# --- 3. SIDEBAR CONTROLS ---
st.sidebar.title("Dashboard Navigation")
st.sidebar.markdown("---")

view_mode = st.sidebar.radio(
    "Select Performance Window:",
    options=["Week to Date (WTD)", "Month to Date (MTD)"],
    index=0,
    help="WTD isolates the latest reporting week. MTD aggregates performance over the active month block within the 5-week window."
)

available_channels = df_5_weeks['Channel'].dropna().unique().tolist()
selected_channels = st.sidebar.multiselect("Filter by Channel:", available_channels, default=available_channels)

# Time Splicing Matrix logic
latest_date = pd.to_datetime(df_5_weeks['Week Start'].max())

if view_mode == "Week to Date (WTD)":
    df_filtered = df_5_weeks[df_5_weeks['Week Start'] == latest_date]
else:
    df_filtered = df_5_weeks[(df_5_weeks['Week Start'].dt.month == latest_date.month) & 
                             (df_5_weeks['Week Start'].dt.year == latest_date.year)]

df_filtered = df_filtered[df_filtered['Channel'].isin(selected_channels)]

# --- 4. HIGH-LEVEL EXECUTIVE SUMMARY ---
st.title("📈 Tele-Counselor (TC) Performance & Growth Dashboard")
st.markdown(f"Displaying data tracking the **last 5 reporting weeks**. Current slice: **{view_mode}** ({latest_date.strftime('%d-%b-%Y')}).")

summary_active = int(df_filtered.drop_duplicates(subset=['Channel'])['Active TCs'].sum()) if view_mode == "WTD" else int(df_filtered['Active TCs'].mean())
summary_new = int(df_filtered['New TCs'].sum())
summary_churn = int(df_filtered['Churn'].dropna().sum())
summary_net = int(df_filtered['Net New Additions'].dropna().sum())

kpi1, kpi2, kpi3, kpi4 = st.columns(4)
kpi1.metric(label="Active TCs Headcount", value=f"{summary_active:,}")
kpi2.metric(label="Gross New TCs", value=f"{summary_new:,}")
kpi3.metric(label="Total Churn Count", value=f"{summary_churn:,}", delta=f"-{summary_churn}" if summary_churn else None, delta_color="inverse")
kpi4.metric(label="Net Growth Velocity", value=f"{summary_net:+d}", delta=f"{summary_net:+d}")

st.markdown("---")

# --- 5. CONDITIONAL FORMATTING GENERATOR ---
def apply_visual_styles(val):
    try:
        if val > 0:
            return 'background-color: #d4edda; color: #155724; font-weight: bold;'
        elif val < 0:
            return 'background-color: #f8d7da; color: #721c24; font-weight: bold;'
    except:
        pass
    return ''

# --- 6. MULTI-TAB VIEW INTERFACE WITH GROUPED BLOCKS ---
tab1, tab2, tab3 = st.tabs(["📊 Channel Wise Performance", "🗺️ Region Wise Performance", "⚡ Productivity & Connectivity"])

with tab1:
    st.markdown("### Channel Wise Performance View (Grouped)")
    st.caption("Rows are grouped chronologically by Channel matching **image_24f63b.png**. Click headers to sort metrics inside or across groups.")
    
    # Sort explicitly by Channel and Week Start to form visual blocks
    ch_display = df_filtered.sort_values(by=["Channel", "Week Start"], ascending=[True, True]).copy()
    
    ch_display = ch_display[[
        "Channel", "Week Start", "Active TCs", "Retained TCs", "New TCs", "Resurrected TCs", "Churn", "Net New Additions"
    ]]
    
    ch_display.insert(2, "June Addition Target", "")
    ch_display['Week Start'] = ch_display['Week Start'].dt.strftime('%d/%m/%Y')
    
    # 🛠️ GROUPING MECHANISM: Set 'Channel' as index so Streamlit groups identical records visually
    ch_grouped = ch_display.set_index(["Channel"])
    
    st.dataframe(
        ch_grouped.style.map(apply_visual_styles, subset=['Net New Additions']),
        use_container_width=True,
        hide_index=False  # Keep True for index grouping column visibility
    )

with tab2:
    st.markdown("### Region Wise Performance View (Grouped)")
    st.caption("Rows are grouped chronologically by geographical matrix matching **image_24f603.png**.")
    
    if "Region" not in df_filtered.columns or df_filtered["Region"].isnull().all():
        df_filtered["Region"] = "Unassigned"
        
    # Sort explicitly by Region and Week Start to form visual blocks
    region_display = df_filtered.sort_values(by=["Region", "Week Start"], ascending=[True, True]).copy()
    
    region_view = region_display[[
        "Region", "Week Start", "Active TCs", "Retained TCs", "New TCs", "Resurrected TCs", "Churn", "Net New Additions"
    ]]
    
    region_view.rename(columns={
        "Week Start": "Start",
        "Active TCs": "TCs",
        "Retained TCs": "Retained TCs",
        "Resurrected TCs": "ed TCs",
        "Net New Additions": "change"
    }, inplace=True)
    
    region_view.insert(2, "Addition Target", "")
    region_view['Start'] = pd.to_datetime(region_view['Start']).dt.strftime('%d/%m/%Y')
    
    # 🛠️ GROUPING MECHANISM: Set 'Region' as index so Streamlit groups identical regions visually
    region_grouped = region_view.set_index(["Region"])
    
    st.dataframe(
        region_grouped.style.map(apply_visual_styles, subset=['change']),
        use_container_width=True,
        hide_index=False
    )

with tab3:
    st.markdown("### TC Operational Health: Connectivity & Productivity")
    
    prod_df = df_filtered.sort_values(by=["Channel"], ascending=True).copy()
    
    prod_df['Connectivity Rate (%)'] = ((prod_df['Connected TCs'] / prod_df['Active TCs']) * 100).replace([np.inf, -np.inf], 0).fillna(0).round(1)
    prod_df['Productivity Rate (%)'] = ((prod_df['Productive TCs'] / prod_df['Active TCs']) * 100).replace([np.inf, -np.inf], 0).fillna(0).round(1)
    
    prod_display = prod_df[[
        "Channel", "Active TCs", "Connected TCs", "Connectivity Rate (%)", "Productive TCs", "Productivity Rate (%)"
    ]].set_index(["Channel"])
    
    st.dataframe(
        prod_display.style.background_gradient(cmap="YlGnBu", subset=['Connectivity Rate (%)', 'Productivity Rate (%)']),
        use_container_width=True,
        hide_index=False
    )
