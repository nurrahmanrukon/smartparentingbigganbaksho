import json
from datetime import date

import pandas as pd
import streamlit as st
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    DateRange,
    Dimension,
    Metric,
    OrderBy,
    RunReportRequest,
)
from google.oauth2 import service_account


PROPERTY_ID = "485333696"

st.set_page_config(
    page_title="Bigganbaksho GA4 Dashboard",
    layout="wide"
)

st.markdown(
    """
    <style>
    .main {
        background-color: #F5F7FA;
    }

    .dashboard-header {
        padding: 28px;
        border-radius: 20px;
        background: linear-gradient(135deg, #0B1F3A 0%, #123C69 50%, #14B8A6 100%);
        color: white;
        margin-bottom: 25px;
        box-shadow: 0 8px 24px rgba(0,0,0,0.12);
    }

    .dashboard-header h1 {
        font-size: 34px;
        margin-bottom: 6px;
    }

    .dashboard-header p {
        font-size: 16px;
        opacity: 0.92;
    }

    div[data-testid="stMetric"] {
        background: white;
        padding: 18px;
        border-radius: 16px;
        border-left: 6px solid #14B8A6;
        box-shadow: 0 4px 14px rgba(0,0,0,0.08);
    }

    div[data-testid="stMetricLabel"] {
        font-size: 15px;
        font-weight: 700;
        color: #0B1F3A;
    }

    div[data-testid="stMetricValue"] {
        font-size: 26px;
        font-weight: 800;
        color: #123C69;
    }

    .section-title {
        font-size: 24px;
        font-weight: 800;
        color: #0B1F3A;
        margin-top: 24px;
        margin-bottom: 10px;
    }

    .info-box {
        background: #FFFFFF;
        border: 1px solid #E5E7EB;
        padding: 16px;
        border-radius: 14px;
        box-shadow: 0 3px 12px rgba(0,0,0,0.05);
        margin-bottom: 18px;
    }
    </style>
    """,
    unsafe_allow_html=True
)

st.markdown(
    """
    <div class="dashboard-header">
        <h1>Bigganbaksho GA4 Traffic Acquisition Dashboard</h1>
        <p>Date-wise Session Source / Medium, Event Count, Key Events, Revenue and Engagement Report</p>
    </div>
    """,
    unsafe_allow_html=True
)


col1, col2, col3, col4 = st.columns(4)

with col1:
    start_date = st.date_input("Start date", date(2026, 1, 1))

with col2:
    end_date = st.date_input("End date", date(2026, 7, 7))

with col3:
    search_text = st.text_input("Search source/medium", "leaflet")

with col4:
    row_limit = st.number_input("Rows limit", min_value=10, max_value=5000, value=1000, step=10)


def seconds_to_min_sec(seconds):
    seconds = int(float(seconds))
    minutes = seconds // 60
    sec = seconds % 60
    return f"{minutes}m {sec}s"


def format_currency(value):
    return f"৳{value:,.2f}"


def format_percent(value):
    return f"{value:.2f}%"


def load_ga4_client():
    service_account_info = json.loads(st.secrets["gcp_service_account_json"])

    credentials = service_account.Credentials.from_service_account_info(
        service_account_info
    )

    return BetaAnalyticsDataClient(credentials=credentials)


def run_ga4_report(client, start_date, end_date, row_limit):
    request = RunReportRequest(
        property=f"properties/{PROPERTY_ID}",
        dimensions=[
            Dimension(name="sessionSourceMedium")
        ],
        metrics=[
            Metric(name="sessions"),
            Metric(name="engagedSessions"),
            Metric(name="engagementRate"),
            Metric(name="userEngagementDuration"),
            Metric(name="eventsPerSession"),

            # Screenshot report metrics
            Metric(name="eventCount"),
            Metric(name="keyEvents"),
            Metric(name="sessionKeyEventRate"),
            Metric(name="totalRevenue"),
        ],
        date_ranges=[
            DateRange(
                start_date=str(start_date),
                end_date=str(end_date)
            )
        ],
        order_bys=[
            OrderBy(
                metric=OrderBy.MetricOrderBy(metric_name="eventCount"),
                desc=True
            )
        ],
        limit=int(row_limit)
    )

    return client.run_report(request)


def response_to_dataframe(response):
    rows = []

    for row in response.rows:
        source_medium = row.dimension_values[0].value

        sessions = int(float(row.metric_values[0].value))
        engaged_sessions = int(float(row.metric_values[1].value))
        engagement_rate = float(row.metric_values[2].value) * 100
        user_engagement_duration = float(row.metric_values[3].value)
        events_per_session = float(row.metric_values[4].value)

        event_count = int(float(row.metric_values[5].value))
        key_events = float(row.metric_values[6].value)
        session_key_event_rate = float(row.metric_values[7].value) * 100
        total_revenue = float(row.metric_values[8].value)

        avg_engagement_time = (
            user_engagement_duration / sessions if sessions > 0 else 0
        )

        rows.append({
            "Session source / medium": source_medium,
            "Sessions": sessions,
            "Engaged sessions": engaged_sessions,
            "Engagement rate": engagement_rate,
            "Average engagement time per session": avg_engagement_time,
            "Events per session": events_per_session,
            "Event count": event_count,
            "Key events": key_events,
            "Session key event rate": session_key_event_rate,
            "Total revenue": total_revenue,
        })

    return pd.DataFrame(rows)


def show_colored_table(df):
    display_df = df.copy()

    styled_df = display_df.style.format({
        "Sessions": "{:,.0f}",
        "Engaged sessions": "{:,.0f}",
        "Engagement rate": "{:.2f}%",
        "Average engagement time per session": lambda x: seconds_to_min_sec(x),
        "Events per session": "{:.2f}",
        "Event count": "{:,.0f}",
        "Key events": "{:,.2f}",
        "Session key event rate": "{:.2f}%",
        "Total revenue": "৳{:,.2f}",
    }).background_gradient(
        subset=["Event count", "Sessions", "Total revenue", "Key events"],
        cmap="YlGnBu"
    )

    st.dataframe(styled_df, use_container_width=True, height=520)


if st.button("Load Colorful Report", type="primary"):
    if start_date > end_date:
        st.error("Start date end date-এর পরে হতে পারে না.")
    else:
        try:
            client = load_ga4_client()
            response = run_ga4_report(client, start_date, end_date, row_limit)
            df = response_to_dataframe(response)

            if df.empty:
                st.warning("এই date range-এ কোনো data পাওয়া যায়নি.")
            else:
                if search_text:
                    df = df[
                        df["Session source / medium"]
                        .str.contains(search_text, case=False, na=False)
                    ]

                if df.empty:
                    st.warning("Search keyword অনুযায়ী কোনো data পাওয়া যায়নি.")
                else:
                    total_sessions = df["Sessions"].sum()
                    total_engaged_sessions = df["Engaged sessions"].sum()
                    total_events = df["Event count"].sum()
                    total_key_events = df["Key events"].sum()
                    total_revenue = df["Total revenue"].sum()

                    overall_engagement_rate = (
                        total_engaged_sessions / total_sessions * 100
                        if total_sessions > 0 else 0
                    )

                    metric_col1, metric_col2, metric_col3, metric_col4, metric_col5 = st.columns(5)

                    with metric_col1:
                        st.metric("Sessions", f"{total_sessions:,.0f}")

                    with metric_col2:
                        st.metric("Event Count", f"{total_events:,.0f}")

                    with metric_col3:
                        st.metric("Key Events", f"{total_key_events:,.2f}")

                    with metric_col4:
                        st.metric("Engagement Rate", f"{overall_engagement_rate:.2f}%")

                    with metric_col5:
                        st.metric("Total Revenue", format_currency(total_revenue))

                    st.markdown('<div class="section-title">Full Traffic Acquisition Report</div>', unsafe_allow_html=True)
                    show_colored_table(df)

                    st.markdown('<div class="section-title">Event Count by Source / Medium</div>', unsafe_allow_html=True)
                    event_chart_df = df[["Session source / medium", "Event count"]].copy()
                    st.bar_chart(event_chart_df.set_index("Session source / medium"))

                    st.markdown('<div class="section-title">Revenue by Source / Medium</div>', unsafe_allow_html=True)
                    revenue_chart_df = df[["Session source / medium", "Total revenue"]].copy()
                    st.bar_chart(revenue_chart_df.set_index("Session source / medium"))

                    st.markdown('<div class="section-title">Key Events by Source / Medium</div>', unsafe_allow_html=True)
                    key_event_chart_df = df[["Session source / medium", "Key events"]].copy()
                    st.bar_chart(key_event_chart_df.set_index("Session source / medium"))

                    download_df = df.copy()
                    download_df["Engagement rate"] = download_df["Engagement rate"].apply(format_percent)
                    download_df["Average engagement time per session"] = download_df[
                        "Average engagement time per session"
                    ].apply(seconds_to_min_sec)
                    download_df["Session key event rate"] = download_df[
                        "Session key event rate"
                    ].apply(format_percent)
                    download_df["Total revenue"] = download_df["Total revenue"].apply(format_currency)

                    csv = download_df.to_csv(index=False).encode("utf-8-sig")

                    st.download_button(
                        label="Download Full CSV Report",
                        data=csv,
                        file_name="bigganbaksho_ga4_traffic_acquisition_report.csv",
                        mime="text/csv"
                    )

        except Exception as e:
            st.error("Report load করা যায়নি.")
            st.code(str(e))
