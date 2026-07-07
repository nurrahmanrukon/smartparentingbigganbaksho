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

st.title("Bigganbaksho GA4 Traffic Acquisition Dashboard")
st.caption("Date-wise GA4 Traffic Acquisition Report")


col1, col2, col3 = st.columns(3)

with col1:
    start_date = st.date_input("Start date", date(2026, 1, 1))

with col2:
    end_date = st.date_input("End date", date(2026, 7, 7))

with col3:
    search_text = st.text_input("Search source/medium", "leaflet")


def seconds_to_min_sec(seconds):
    seconds = int(float(seconds))
    minutes = seconds // 60
    sec = seconds % 60
    return f"{minutes}m {sec}s"


def load_ga4_client():
    service_account_info = json.loads(st.secrets["gcp_service_account_json"])

    credentials = service_account.Credentials.from_service_account_info(
        service_account_info
    )

    client = BetaAnalyticsDataClient(credentials=credentials)
    return client


def run_ga4_report(client, start_date, end_date):
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
        ],
        date_ranges=[
            DateRange(
                start_date=str(start_date),
                end_date=str(end_date)
            )
        ],
        order_bys=[
            OrderBy(
                metric=OrderBy.MetricOrderBy(metric_name="sessions"),
                desc=True
            )
        ],
        limit=1000
    )

    response = client.run_report(request)
    return response


def response_to_dataframe(response):
    rows = []

    for row in response.rows:
        source_medium = row.dimension_values[0].value

        sessions = int(float(row.metric_values[0].value))
        engaged_sessions = int(float(row.metric_values[1].value))
        engagement_rate = float(row.metric_values[2].value) * 100
        user_engagement_duration = float(row.metric_values[3].value)
        events_per_session = float(row.metric_values[4].value)

        avg_engagement_time = (
            user_engagement_duration / sessions if sessions > 0 else 0
        )

        rows.append({
            "Session source / medium": source_medium,
            "Sessions": sessions,
            "Engaged sessions": engaged_sessions,
            "Engagement rate": f"{engagement_rate:.2f}%",
            "Average engagement time per session": seconds_to_min_sec(avg_engagement_time),
            "Events per session": round(events_per_session, 2),
        })

    return pd.DataFrame(rows)


if st.button("Load Report"):
    if start_date > end_date:
        st.error("Start date end date-এর পরে হতে পারে না.")
    else:
        try:
            client = load_ga4_client()
            response = run_ga4_report(client, start_date, end_date)
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

                    metric_col1, metric_col2, metric_col3 = st.columns(3)

                    with metric_col1:
                        st.metric("Total Sessions", f"{total_sessions:,}")

                    with metric_col2:
                        st.metric("Total Engaged Sessions", f"{total_engaged_sessions:,}")

                    with metric_col3:
                        if total_sessions > 0:
                            overall_engagement_rate = (
                                total_engaged_sessions / total_sessions
                            ) * 100
                        else:
                            overall_engagement_rate = 0

                        st.metric(
                            "Overall Engagement Rate",
                            f"{overall_engagement_rate:.2f}%"
                        )

                    st.subheader("Report Table")
                    st.dataframe(df, use_container_width=True)

                    st.subheader("Sessions by Source / Medium")
                    chart_df = df.copy()
                    chart_df["Sessions"] = pd.to_numeric(chart_df["Sessions"])
                    st.bar_chart(
                        chart_df.set_index("Session source / medium")["Sessions"]
                    )

                    csv = df.to_csv(index=False).encode("utf-8-sig")

                    st.download_button(
                        label="Download CSV",
                        data=csv,
                        file_name="ga4_traffic_acquisition_report.csv",
                        mime="text/csv"
                    )

        except Exception as e:
            st.error("Report load করা যায়নি.")
            st.code(str(e))
