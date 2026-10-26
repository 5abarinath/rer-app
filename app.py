"""Real Exchange Rate explorer built on IMF SDMX 3.0 data.

S(t)   = units of Country 2 currency per one unit of Country 1 currency
RER(t) = S(t) * P1(t) / P2(t)
Real Index(t) = 100 * RER(t) / RER*, with RER* the mean RER(t) over valid
months in the user-selected sample.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
from plotly.subplots import make_subplots

IMF_BASE = "https://api.imf.org/external/sdmx/3.0"
CPI_FLOW = "IMF.STA/CPI"
ER_FLOW = "IMF.STA/ER"
CPI_KEY = "{iso}.CPI._T.IX.M"
ER_KEY = "{iso}.XDC_USD.PA_RT.M"
# SDMX 3.0 "latest version" tokens; the first that works is used.
VERSION_TOKENS = ("+", "~")
START_DATE = pd.Timestamp("1976-01-01")
EURO_AREA = "G163"
USA = "USA"

# IMF country codes (ISO3 unless noted) plus the Euro area aggregate.
COUNTRIES: dict[str, str] = {
    "AFG": "Afghanistan", "ALB": "Albania", "DZA": "Algeria", "AGO": "Angola",
    "ATG": "Antigua and Barbuda", "ARG": "Argentina", "ARM": "Armenia",
    "ABW": "Aruba", "AUS": "Australia", "AUT": "Austria", "AZE": "Azerbaijan",
    "BHS": "Bahamas, The", "BHR": "Bahrain", "BGD": "Bangladesh",
    "BRB": "Barbados", "BLR": "Belarus", "BEL": "Belgium", "BLZ": "Belize",
    "BEN": "Benin", "BTN": "Bhutan", "BOL": "Bolivia",
    "BIH": "Bosnia and Herzegovina", "BWA": "Botswana", "BRA": "Brazil",
    "BRN": "Brunei Darussalam", "BGR": "Bulgaria", "BFA": "Burkina Faso",
    "BDI": "Burundi", "CPV": "Cabo Verde", "KHM": "Cambodia", "CMR": "Cameroon",
    "CAN": "Canada", "CAF": "Central African Republic", "TCD": "Chad",
    "CHL": "Chile", "CHN": "China, P.R.: Mainland", "HKG": "China, P.R.: Hong Kong",
    "MAC": "China, P.R.: Macao", "COL": "Colombia", "COM": "Comoros",
    "COD": "Congo, Democratic Republic of the", "COG": "Congo, Republic of",
    "CRI": "Costa Rica", "CIV": "Côte d'Ivoire", "HRV": "Croatia",
    "CYP": "Cyprus", "CZE": "Czech Republic", "DNK": "Denmark",
    "DJI": "Djibouti", "DMA": "Dominica", "DOM": "Dominican Republic",
    "ECU": "Ecuador", "EGY": "Egypt", "SLV": "El Salvador",
    "GNQ": "Equatorial Guinea", "ERI": "Eritrea", "EST": "Estonia",
    "SWZ": "Eswatini", "ETH": "Ethiopia", "FJI": "Fiji", "FIN": "Finland",
    "FRA": "France", "GAB": "Gabon", "GMB": "Gambia, The", "GEO": "Georgia",
    "DEU": "Germany", "GHA": "Ghana", "GRC": "Greece", "GRD": "Grenada",
    "GTM": "Guatemala", "GIN": "Guinea", "GNB": "Guinea-Bissau", "GUY": "Guyana",
    "HTI": "Haiti", "HND": "Honduras", "HUN": "Hungary", "ISL": "Iceland",
    "IND": "India", "IDN": "Indonesia", "IRN": "Iran", "IRQ": "Iraq",
    "IRL": "Ireland", "ISR": "Israel", "ITA": "Italy", "JAM": "Jamaica",
    "JPN": "Japan", "JOR": "Jordan", "KAZ": "Kazakhstan", "KEN": "Kenya",
    "KIR": "Kiribati", "XKX": "Kosovo", "KOR": "Korea, Republic of",
    "KWT": "Kuwait", "KGZ": "Kyrgyz Republic", "LAO": "Lao P.D.R.",
    "LVA": "Latvia", "LBN": "Lebanon", "LSO": "Lesotho", "LBR": "Liberia",
    "LBY": "Libya", "LTU": "Lithuania", "LUX": "Luxembourg",
    "MDG": "Madagascar", "MWI": "Malawi", "MYS": "Malaysia", "MDV": "Maldives",
    "MLI": "Mali", "MLT": "Malta", "MHL": "Marshall Islands", "MRT": "Mauritania",
    "MUS": "Mauritius", "MEX": "Mexico", "FSM": "Micronesia, Fed. States of",
    "MDA": "Moldova", "MNG": "Mongolia", "MNE": "Montenegro", "MAR": "Morocco",
    "MOZ": "Mozambique", "MMR": "Myanmar", "NAM": "Namibia", "NRU": "Nauru",
    "NPL": "Nepal", "NLD": "Netherlands", "NZL": "New Zealand", "NIC": "Nicaragua",
    "NER": "Niger", "NGA": "Nigeria", "MKD": "North Macedonia", "NOR": "Norway",
    "OMN": "Oman", "PAK": "Pakistan", "PLW": "Palau", "PAN": "Panama",
    "PNG": "Papua New Guinea", "PRY": "Paraguay", "PER": "Peru",
    "PHL": "Philippines", "POL": "Poland", "PRT": "Portugal", "QAT": "Qatar",
    "ROU": "Romania", "RUS": "Russian Federation", "RWA": "Rwanda",
    "WSM": "Samoa", "SMR": "San Marino", "STP": "São Tomé and Príncipe",
    "SAU": "Saudi Arabia", "SEN": "Senegal", "SRB": "Serbia", "SYC": "Seychelles",
    "SLE": "Sierra Leone", "SGP": "Singapore", "SVK": "Slovak Republic",
    "SVN": "Slovenia", "SLB": "Solomon Islands", "SOM": "Somalia",
    "ZAF": "South Africa", "SSD": "South Sudan", "ESP": "Spain",
    "LKA": "Sri Lanka", "KNA": "St. Kitts and Nevis", "LCA": "St. Lucia",
    "VCT": "St. Vincent and the Grenadines", "SDN": "Sudan", "SUR": "Suriname",
    "SWE": "Sweden", "CHE": "Switzerland", "SYR": "Syria", "TWN": "Taiwan Province of China",
    "TJK": "Tajikistan", "TZA": "Tanzania", "THA": "Thailand",
    "TLS": "Timor-Leste", "TGO": "Togo", "TON": "Tonga",
    "TTO": "Trinidad and Tobago", "TUN": "Tunisia", "TUR": "Türkiye",
    "TKM": "Turkmenistan", "TUV": "Tuvalu", "UGA": "Uganda", "UKR": "Ukraine",
    "ARE": "United Arab Emirates", "GBR": "United Kingdom", "USA": "United States",
    "URY": "Uruguay", "UZB": "Uzbekistan", "VUT": "Vanuatu",
    "VEN": "Venezuela", "VNM": "Vietnam", "WBG": "West Bank and Gaza",
    "YEM": "Yemen", "ZMB": "Zambia", "ZWE": "Zimbabwe",
    EURO_AREA: "Euro area",
}


class IMFDataError(Exception):
    """Raised when a series cannot be retrieved or parsed."""


# --------------------------------------------------------------------------
# Fetching and parsing
# --------------------------------------------------------------------------

_PERIOD_RE = re.compile(r"^(\d{4})-?M?(\d{2})$")


def _parse_period(label: str) -> pd.Timestamp | None:
    """Turn '1999-M01' / '1999-01' into the first day of that month."""
    m = _PERIOD_RE.match(str(label).strip())
    if not m:
        return None
    year, month = int(m.group(1)), int(m.group(2))
    if not 1 <= month <= 12:
        return None
    return pd.Timestamp(year=year, month=month, day=1)


def parse_sdmx_csv(text: str) -> pd.Series:
    """Parse an SDMX-CSV payload into a monthly float series."""
    df = pd.read_csv(io.StringIO(text), dtype=str)
    cols = {c.strip().upper(): c for c in df.columns}
    if "TIME_PERIOD" not in cols or "OBS_VALUE" not in cols:
        raise IMFDataError("Unexpected CSV layout (no TIME_PERIOD/OBS_VALUE).")
    return _to_series(df[cols["TIME_PERIOD"]], df[cols["OBS_VALUE"]])


def parse_sdmx_json(payload: dict) -> pd.Series:
    """Parse an SDMX-JSON data message (time series at observation level)."""
    try:
        data = payload["data"]
        structure = data["structures"][0]
        obs_dims = structure["dimensions"].get("observation", [])
        time_values = [v["id"] for v in obs_dims[0]["values"]]
        series_map = data["dataSets"][0]["series"]
    except (KeyError, IndexError, TypeError) as exc:
        raise IMFDataError("Unexpected JSON layout.") from exc
    if not series_map:
        raise IMFDataError("Empty series.")
    # The key restricts the query to one series; take the first.
    observations = next(iter(series_map.values())).get("observations", {})
    periods, values = [], []
    for idx, obs in observations.items():
        periods.append(time_values[int(idx)])
        values.append(obs[0])
    return _to_series(pd.Series(periods), pd.Series(values))


def _to_series(periods: pd.Series, values: pd.Series) -> pd.Series:
    idx = [_parse_period(p) for p in periods]
    s = pd.Series(pd.to_numeric(values, errors="coerce").to_numpy(), index=idx, dtype=float)
    s = s[[i is not None for i in s.index]]
    if s.empty:
        raise IMFDataError("No monthly observations in response.")
    s.index = pd.DatetimeIndex(s.index)
    s = s[~s.index.duplicated(keep="last")].sort_index()
    return s


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def fetch_series(flow: str, key: str) -> pd.Series:
    """Download one monthly series from the IMF API (all history, from 1976)."""
    last_error = "unknown error"
    for version in VERSION_TOKENS:
        url = f"{IMF_BASE}/data/dataflow/{flow}/{version}/{key}"
        for accept, parser in (
            ("application/vnd.sdmx.data+csv;version=2.0.0", "csv"),
            ("application/vnd.sdmx.data+json;version=2.0.0", "json"),
        ):
            try:
                resp = requests.get(url, headers={"Accept": accept}, timeout=60)
            except requests.RequestException as exc:
                last_error = f"network error: {exc}"
                continue
            if resp.status_code == 404:
                last_error = "series not found (HTTP 404)"
                continue
            if resp.status_code != 200:
                last_error = f"HTTP {resp.status_code}"
                continue
            try:
                s = parse_sdmx_csv(resp.text) if parser == "csv" else parse_sdmx_json(resp.json())
            except (IMFDataError, ValueError) as exc:
                last_error = str(exc)
                continue
            return s[s.index >= START_DATE]
    raise IMFDataError(f"{key}: {last_error}")


def load_country(iso: str) -> tuple[pd.Series, pd.Series]:
    """Return (CPI index, local-currency units per USD) for a country."""
    cpi = fetch_series(CPI_FLOW, CPI_KEY.format(iso=iso))
    if iso == USA:
        # The dollar is the numeraire: 1 USD per USD in every month.
        er = pd.Series(1.0, index=cpi.index)
    else:
        er = fetch_series(ER_FLOW, ER_KEY.format(iso=iso))
    return cpi, er


# --------------------------------------------------------------------------
# Calculations
# --------------------------------------------------------------------------

def build_panel(
    cpi1: pd.Series, er1: pd.Series, cpi2: pd.Series, er2: pd.Series
) -> pd.DataFrame:
    """Align raw series on a complete monthly grid and compute S and RER.

    er1/er2 are local-currency units per USD, so units of Country 2 currency
    per unit of Country 1 currency is S = er2 / er1.
    """
    frames = {"CPI_1": cpi1, "CPI_2": cpi2, "XDC_per_USD_1": er1, "XDC_per_USD_2": er2}
    start = max(START_DATE, min(s.index.min() for s in frames.values()))
    end = max(s.index.max() for s in frames.values())
    grid = pd.date_range(start, end, freq="MS")
    df = pd.DataFrame({name: s.reindex(grid) for name, s in frames.items()})
    df.index.name = "date"
    df = df.where(df > 0)  # non-positive values are not usable
    df["S"] = df["XDC_per_USD_2"] / df["XDC_per_USD_1"]
    df["RER"] = df["S"] * df["CPI_1"] / df["CPI_2"]
    df["valid"] = df["RER"].notna()
    return df


def apply_sample(panel: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> tuple[pd.DataFrame, float]:
    """Slice the sample and compute RER* and the Real Index within it."""
    sample = panel.loc[start:end].copy()
    rer_star = sample.loc[sample["valid"], "RER"].mean()
    sample["RER_star"] = rer_star
    sample["Real_Index"] = 100 * sample["RER"] / rer_star
    return sample, rer_star


# --------------------------------------------------------------------------
# Charts
# --------------------------------------------------------------------------

def make_chart(sample: pd.DataFrame, mode: str, c1: str, c2: str) -> go.Figure:
    nominal_label = f"Nominal S: {c2} per 1 {c1}"
    real = go.Scatter(
        x=sample.index, y=sample["Real_Index"], name="Real Index (RER* = 100)",
        mode="lines", connectgaps=False, line=dict(color="#1f77b4"),
    )
    nominal = go.Scatter(
        x=sample.index, y=sample["S"], name=nominal_label,
        mode="lines", connectgaps=False, line=dict(color="#d62728"),
    )
    if mode == "Both":
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(real, secondary_y=False)
        fig.add_trace(nominal, secondary_y=True)
        fig.update_yaxes(title_text="Real Index", secondary_y=False)
        fig.update_yaxes(title_text=nominal_label, secondary_y=True, showgrid=False)
    else:
        fig = go.Figure(real if mode == "Real" else nominal)
        fig.update_yaxes(title_text="Real Index" if mode == "Real" else nominal_label)
    if mode in ("Real", "Both"):
        fig.add_hline(y=100, line_dash="dot", line_color="gray", opacity=0.6,
                      **({"secondary_y": False} if mode == "Both" else {}))
    fig.update_layout(
        hovermode="x unified", height=520, margin=dict(l=10, r=10, t=30, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
    )
    fig.update_xaxes(title_text="Month")
    return fig


# --------------------------------------------------------------------------
# UI
# --------------------------------------------------------------------------

def label(iso: str) -> str:
    return f"{COUNTRIES[iso]} ({iso})"


def main() -> None:
    st.set_page_config(page_title="IMF Real Exchange Rate", layout="wide")
    st.title("Real Exchange Rate Explorer")
    st.caption(
        "Monthly IMF CPI and exchange-rate data. S(t) = units of Country 2 currency per "
        "one unit of Country 1 currency; RER(t) = S(t) × P1(t) / P2(t)."
    )

    codes = sorted(COUNTRIES, key=lambda c: COUNTRIES[c])
    col_a, col_b = st.columns(2)
    iso1 = col_a.selectbox("Country 1", codes, index=codes.index(USA), format_func=label)
    iso2 = col_b.selectbox("Country 2", codes, index=codes.index(EURO_AREA), format_func=label)
    if iso1 == iso2:
        st.warning("Choose two different countries.")
        st.stop()

    with st.spinner("Fetching IMF data..."):
        try:
            cpi1, er1 = load_country(iso1)
            cpi2, er2 = load_country(iso2)
        except IMFDataError as exc:
            st.error(f"Could not retrieve IMF data: {exc}")
            st.stop()

    panel = build_panel(cpi1, er1, cpi2, er2)
    valid_months = panel.index[panel["valid"]]
    if valid_months.empty:
        st.error("The two countries share no month with CPI and exchange-rate data for all series.")
        st.stop()

    first, last = valid_months.min(), valid_months.max()
    months = list(pd.date_range(first, last, freq="MS"))
    start, end = st.select_slider(
        "Sample period (start and end month)",
        options=months,
        value=(months[0], months[-1]),
        format_func=lambda d: d.strftime("%b %Y"),
    )

    sample, rer_star = apply_sample(panel, start, end)
    n_valid = int(sample["valid"].sum())
    gaps = len(sample) - n_valid

    m1, m2, m3 = st.columns(3)
    m1.metric("RER* (mean RER over valid months)", f"{rer_star:,.4f}")
    m2.metric("Valid months used", f"{n_valid}")
    m3.metric("Months with missing data", f"{gaps}")
    if gaps:
        st.info(
            f"{gaps} month(s) in the sample lack one or more of the four inputs; "
            "they are excluded from RER* and appear as gaps in the chart."
        )
    if first > START_DATE:
        st.caption(f"Data coverage for this pair begins {first:%b %Y} (requested from Jan 1976).")

    mode = st.radio("Series to plot", ["Real", "Nominal", "Both"], horizontal=True)
    st.plotly_chart(make_chart(sample, mode, iso1, iso2), width="stretch")

    out = sample.rename(columns={
        "CPI_1": f"P1_CPI_{iso1}", "CPI_2": f"P2_CPI_{iso2}",
        "XDC_per_USD_1": f"{iso1}_currency_per_USD", "XDC_per_USD_2": f"{iso2}_currency_per_USD",
        "S": f"S_{iso2}_per_{iso1}", "valid": "valid_month",
    }).reset_index()
    out["date"] = out["date"].dt.strftime("%Y-%m")
    st.download_button(
        "Download CSV (selected sample)",
        out.to_csv(index=False).encode("utf-8"),
        file_name=f"rer_{iso1}_{iso2}_{start:%Y%m}_{end:%Y%m}.csv",
        mime="text/csv",
    )
    with st.expander("Show data"):
        st.dataframe(out, width="stretch")


if __name__ == "__main__":
    main()
