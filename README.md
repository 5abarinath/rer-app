# IMF Real Exchange Rate Explorer

A Streamlit app that computes and plots the bilateral real exchange rate (RER) for any two
IMF countries (or the Euro area) from monthly IMF CPI and exchange-rate data.

## Method

- `S(t)`: units of Country 2 currency per one unit of Country 1 currency.
- IMF exchange rates are local-currency units per USD (`e1`, `e2`), so `S(t) = e2(t) / e1(t)`.
  The United States is the numeraire (`e = 1`).
- `RER(t) = S(t) × P1(t) / P2(t)`, where `P1`, `P2` are monthly CPI indices.
- `RER*` is the mean of `RER(t)` over valid months in the selected start–end window, and
  `Real Index(t) = 100 × RER(t) / RER*`. It is recomputed whenever the window changes.
- Nominal `S(t)` is plotted in actual currency units (not normalised).
- A month is *valid* only if all four inputs (P1, P2, e1, e2) are present and positive.
  Other months show as gaps and are excluded from `RER*`.

## Data

IMF SDMX 3.0 API (`https://api.imf.org/external/sdmx/3.0`), history from January 1976 where available:

| Data | Dataflow | Key |
|------|----------|-----|
| CPI | `IMF.STA/CPI` | `{ISO3}.CPI._T.IX.M` |
| Exchange rate | `IMF.STA/ER` | `{ISO3}.XDC_USD.PA_RT.M` |

The Euro area uses code `G163`. Coverage varies by country; the sample slider is limited to the
span in which both countries have all four inputs. The country list is built in (`COUNTRIES` in
`app.py`); a country with no series returns a clear error. Responses are cached for 6 hours.

## Run

Requires Python 3.12+.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Features

- Country 1 / Country 2 selectors and a start/end month slider.
- Chart modes **Real**, **Nominal**, **Both** (Both uses separate y-axes).
- CSV download of every month in the sample: inputs, `S`, `RER`, `RER*`, `Real_Index`, `valid_month`.

## Caveats

- The dataflow IDs and version token (`+`, falling back to `~`) follow IMF's SDMX 3.0 conventions;
  adjust `CPI_FLOW`, `ER_FLOW` and `VERSION_TOKENS` in `app.py` if the IMF changes them.
- For euro members, pre-adoption exchange rates are as reported by the IMF (legacy currency or
  euro-converted); check the series if you rely on pre-1999 data.
