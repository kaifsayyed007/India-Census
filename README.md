# India District Explorer

An interactive web app built with **Streamlit** and **Plotly** that lets you explore Indian census-style data at the district level. Pick a state (or all of India), choose two parameters, and see them on a map, in rankings, in a scatter plot and in a table.

This README is written for beginners. It explains how to run the project, how the code works step by step, and why each decision was made.

---

## Table of contents

1. [What the app does](#1-what-the-app-does)
2. [Project files](#2-project-files)
3. [Setup and running](#3-setup-and-running)
4. [How Streamlit works (read this first)](#4-how-streamlit-works-read-this-first)
5. [The dataset](#5-the-dataset)
6. [Code workflow, step by step](#6-code-workflow-step-by-step)
7. [The `get_values` function in detail](#7-the-get_values-function-in-detail)
8. [Understanding the tabs](#8-understanding-the-tabs)
9. [Changes made to the original code](#9-changes-made-to-the-original-code)
10. [Known limitations and checks](#10-known-limitations-and-checks)
11. [Troubleshooting](#11-troubleshooting)
12. [Ideas for next steps](#12-ideas-for-next-steps)
13. [Glossary](#13-glossary)

---

## 1. What the app does

You choose:

- a **state** (or "Overall India"),
- a **primary parameter**, which controls bubble size on the map,
- a **secondary parameter**, which controls bubble colour,
- whether to show values as a **% share** or as raw counts,
- a colour scale and a map style.

The app then shows:

- **Summary cards:** number of districts, average value, highest district, correlation.
- **Map tab:** one bubble per district.
- **Rankings tab:** top and bottom districts for the primary parameter.
- **Relationship tab:** a scatter plot of primary against secondary.
- **Data tab:** a table you can download as CSV.

## 2. Project files

```
your-project/
├── app.py            # the whole application
├── india.csv         # the dataset (517 districts, 103 columns)
├── requirements.txt  # the Python libraries needed
└── README.md         # this file
```

## 3. Setup and running

### Step 1: Install Python
You need Python 3.9 or newer. Check with:

```bash
python --version
```

### Step 2 (recommended): Create a virtual environment
A virtual environment keeps this project's libraries separate from other projects.

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### Step 3: Install the libraries

```bash
pip install -r requirements.txt
```

### Step 4: Run the app

Make sure `app.py` and `india.csv` are in the same folder, then:

```bash
streamlit run app.py
```

Your browser opens at `http://localhost:8501`. To stop the app, press `Ctrl + C` in the terminal.

### What is in `requirements.txt`?

| Library | Why it is needed |
|---|---|
| `streamlit` (1.26 or newer) | Builds the web interface. The `st.sidebar.toggle` widget needs 1.26+. |
| `pandas` | Loads the CSV and works with tables of data. |
| `numpy` | Maths helpers (zoom calculation, handling infinity). |
| `plotly` (5.24 or newer) | Draws the charts. `px.scatter_map` needs 5.24+. |

## 4. How Streamlit works (read this first)

Streamlit has one idea that surprises most beginners:

> **Every time you click or change any widget, Streamlit re-runs your entire script from top to bottom.**

This explains several choices in the code:

- **Caching (`@st.cache_data`):** because the script re-runs on every click, we do not want to re-read the CSV from disk each time. Caching reads it once and remembers it.
- **No "Plot Graph" button:** since the script re-runs anyway, the map can update the moment you change a selection. A plain button would also forget its "pressed" state on the next re-run.
- **Widgets return their current value:** `selected_state = st.sidebar.selectbox(...)` gives you the currently chosen value as a normal Python variable. The rest of the script just uses it.

## 5. The dataset

`india.csv` has **517 rows (districts)** and **103 columns**.

| Kind of column | Examples | Purpose |
|---|---|---|
| Identifiers | `State`, `District`, `District code`, `State name` | Say which district a row is |
| Coordinates | `Latitude`, `Longitude` | Where to draw the bubble |
| Totals | `Population`, `Households` | The base for percentages |
| Counts of people | `Literate`, `Muslims`, `Graduate_Education`, `Workers` | Number of people in a group |
| Counts of households | `Households_with_Internet`, `Households_with_Television` | Number of households with something |
| Rates | `Literacy_rate`, `Sex_ratio` | Already a ratio or percentage |

The difference between these kinds matters, because it decides how each column is converted to a percentage.

## 6. Code workflow, step by step

The script in `app.py` runs in this order.

### Step 1: Imports and page setup

```python
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="India District Explorer", layout="wide")
```

- The four imports bring in the libraries. The short names (`np`, `pd`, `px`, `st`) are conventions everyone uses.
- `st.set_page_config` must be the **first** Streamlit command. `layout="wide"` uses the full browser width. `page_title` is the browser tab text.

### Step 2: Constants

```python
ID_COLS = ["State", "District", "Latitude", "Longitude", "District code", "State name"]
RAW_ONLY = ["Population", "Households", "Literacy_rate", "Sex_ratio", "Total_Power_Parity"]
```

- `ID_COLS` lists columns that are identifiers or coordinates. They are not statistics, so they are kept out of the parameter dropdowns.
- `RAW_ONLY` lists columns that are already totals or rates. Converting them to a percentage would give meaningless numbers (for example, literacy rate divided by population).

### Step 3: Helper functions

Small reusable functions, defined once and used later.

**`load_data()`**

```python
@st.cache_data
def load_data():
    df = pd.read_csv("india.csv")
    return df.dropna(subset=["Latitude", "Longitude"])
```

- `@st.cache_data` is a decorator. It tells Streamlit to run the function once and reuse the result.
- `pd.read_csv` loads the file into a table (a DataFrame).
- `dropna(subset=[...])` removes any row with missing coordinates, because it cannot be drawn on a map.

**`metric_options(df)`**

```python
def metric_options(df):
    return sorted(c for c in df.select_dtypes("number").columns if c not in ID_COLS)
```

Returns the sorted list of numeric columns, excluding the ID columns. This is what fills the dropdowns. (Your original code used `df.columns[2:]`, which wrongly included latitude, longitude and text columns.)

**`pretty(col)`**

```python
def pretty(col):
    return col.replace("_", " ")
```

Turns `Households_with_Internet` into `Households with Internet` for display.

**`get_values(df, col, normalise)`**

Converts a column to a percentage when appropriate. It is the most important function, so it has its own section below (section 7).

### Step 4: Load the data

```python
df = load_data()
metrics = metric_options(df)
```

`df` is the full table and `metrics` is the list of column names the user can choose from.

### Step 5: Build the sidebar

```python
selected_state = st.sidebar.selectbox("State", states)
primary   = st.sidebar.selectbox("Primary parameter (bubble size)", metrics, ...)
secondary = st.sidebar.selectbox("Secondary parameter (colour)", metrics, ...)
normalise = st.sidebar.toggle("Show as % share (fairer across districts)", value=True)
palette   = st.sidebar.selectbox("Colour scale", [...])
basemap   = st.sidebar.selectbox("Map style", [...])
```

- `states = ["Overall India"] + sorted(df["State"].unique())` builds the state list, with "Overall India" first.
- `format_func=pretty` changes only how names *look* in the dropdown. The value you get back is still the real column name.
- `index=...` sets the default choice (Population and Literacy_rate), so the first screen already shows something useful. The `if ... in metrics else 0` guard stops a crash if a column is ever missing.
- `st.sidebar.toggle` is an on/off switch. It returns `True` or `False`.

### Step 6: Prepare the data to display

```python
view = df if selected_state == "Overall India" else df[df["State"] == selected_state]
view = view.copy()
view["_p"], p_label = get_values(view, primary, normalise)
view["_s"], s_label = get_values(view, secondary, normalise)
view = view.replace([np.inf, -np.inf], np.nan)
view["_size"] = view["_p"].fillna(0).clip(lower=0)
```

Line by line:

1. `view` is the rows to show: everything, or just the chosen state.
2. `.copy()` avoids a pandas warning about editing a slice of another table.
3. `_p` and `_s` are new **working columns** holding the primary and secondary values after conversion. Because they have fixed names, every chart below works the same way regardless of which parameter the user picked.
4. `get_values` returns two things (the numbers and a label), and Python unpacks them into the column and the label variable.
5. Dividing by zero (for example a district with 0 households) gives infinity, so `replace` turns infinity into "missing" (NaN).
6. `_size` is the bubble size. Plotly cannot size a bubble with NaN or a negative number, so NaN becomes 0 and negatives are clipped to 0.

### Step 7: Choose map centre and zoom

```python
if selected_state == "Overall India":
    center, zoom = {"lat": 22.5, "lon": 79.0}, 3.6
else:
    span = max(np.ptp(view["Latitude"]), np.ptp(view["Longitude"]), 1)
    center = {"lat": view["Latitude"].mean(), "lon": view["Longitude"].mean()}
    zoom = float(np.clip(7 - np.log2(span), 3.5, 8))
```

- For all of India, a fixed centre and zoom are used.
- For a state, the centre is the **average** latitude and longitude of its districts.
- `np.ptp` ("peak to peak") is the maximum minus the minimum. It measures how spread out the state's districts are.
- A larger spread should mean a lower zoom (zoomed out), and a smaller spread a higher zoom. `7 - np.log2(span)` does this smoothly.
- `np.clip(..., 3.5, 8)` keeps the zoom between 3.5 and 8.
- The `1` inside `max(...)` stops `log2` from receiving a tiny or zero value.

### Step 8: Title and summary cards

```python
st.title(f"{selected_state}: {p_label} vs {s_label}")
c1, c2, c3, c4 = st.columns(4)
```

`st.columns(4)` creates four side-by-side slots. Each one gets a `.metric(...)` card:

1. **Districts:** `len(view)`, the number of rows.
2. **Average:** the mean of `_p`.
3. **Highest district:** `idxmax()` finds the row with the largest value, and `view.loc[...]` fetches that row so its district name can be shown.
4. **Correlation:** `view["_p"].corr(view["_s"])`. Near +1 or -1 means a strong relationship, near 0 means weak. If primary and secondary are the same column, it shows 1.0. `pd.notna(...)` guards against a missing result.

### Step 9: Tabs

```python
tab_map, tab_rank, tab_rel, tab_data = st.tabs(["Map", "Rankings", "Relationship", "Data"])
```

Each `with tab_x:` block puts content inside that tab. See section 8 for what each one does.

## 7. The `get_values` function in detail

```python
def get_values(df, col, normalise):
    """Raw counts are mostly just 'big districts are big'. Convert to % share."""
    if not normalise or col in RAW_ONLY:
        return df[col].astype(float), pretty(col)
    if "Household" in col or "household" in col:
        return df[col] / df["Households"] * 100, f"{pretty(col)} (% of households)"
    return df[col] / df["Population"] * 100, f"{pretty(col)} (% of population)"
```

### The problem it solves

Compare two districts:

| District | Population | Households with Internet |
|---|---|---|
| A | 5,000,000 | 500,000 |
| B | 500,000 | 100,000 |

In raw counts, A looks five times better. But relative to its size, B has far more internet access. Raw counts mostly show "big districts have more of everything". Percentages show what is actually different.

### Every part explained

- **`def`** defines a function (a reusable block of code with a name).
- **`df`** is the input table.
- **`col`** is the input column name, for example `"Households_with_Internet"`.
- **`normalise`** is `True` (give percentages) or `False` (give raw counts).
- **The text in triple quotes** is a docstring, a note for humans that Python ignores.
- **`if not normalise or col in RAW_ONLY:`** means "if percentages are switched off, OR this column is a special one". In that case it returns the raw numbers.
- **`df[col].astype(float)`** picks the column and converts it to decimal numbers.
- **`return a, b`** returns two things at once: the numbers and a label.
- **`"Household" in col`** checks whether the column name contains the word "Household". If so, the base is total households.
- **`df[col] / df["Households"] * 100`** divides each district's value by that district's households, row by row, then multiplies by 100 to get a percentage.
- **`f"..."`** is an f-string. Anything inside `{}` is replaced with its value, so `f"{pretty(col)} (% of households)"` becomes something like `Households with Internet (% of households)`.
- **The last `return`** has no `if` because anything reaching it is a count of people, so it divides by `Population`.

### How it is used

```python
view["_p"], p_label = get_values(view, primary, normalise)
```

The function returns two things, and Python unpacks them: the numbers into the `_p` column, the label into `p_label`.

## 8. Understanding the tabs

### Map tab

```python
fig = px.scatter_map(view, lat="Latitude", lon="Longitude",
                     size="_size", color="_s", hover_name="District", ...)
```

- Each district becomes one bubble at its latitude and longitude.
- `size="_size"` makes bubble size follow the primary parameter.
- `color="_s"` makes colour follow the secondary parameter.
- `hover_name="District"` makes the district name the bold title in the tooltip.
- `hover_data` controls the extra tooltip lines. `True` shows a field, `False` hides it, and a string like `":,.2f"` formats it with thousands separators and 2 decimals.
- `labels` replaces `_p` and `_s` with readable names in tooltips and the colour bar.

### Rankings tab

- The slider chooses `n` (5 to 25).
- `nlargest(n, "_p")` and `nsmallest(n, "_p")` pick the top and bottom n rows.
- A `for` loop draws both bar charts, so the drawing code is written only once.
- `orientation="h"` makes horizontal bars, which suit long district names.

### Relationship tab

A scatter plot of primary (x-axis) against secondary (y-axis), one dot per district. For all of India the dots are coloured by state, so you can see whether a pattern is general or limited to some states.

### Data tab

- Shows the filtered table sorted by the primary value.
- `.rename(columns=labels)` swaps `_p` and `_s` for readable column names.
- `st.download_button` exports exactly the table you are looking at as a CSV file.

## 9. Changes made to the original code

| Original | Problem | Fix |
|---|---|---|
| `sorted(df.columns[2:])` for dropdowns | Included Latitude, Longitude, codes and a text column | `metric_options()` keeps only numeric, non-ID columns |
| Reading the CSV on every run | Slow, repeated work | `@st.cache_data` |
| Raw counts for bubble size | Big districts always dominate | `get_values()` converts to % share |
| "Plot Graph" button | Extra click, and state resets on re-run | Removed; the map updates instantly |
| Fixed `zoom=5` for states | Too far in or out depending on state size | Zoom computed from the spread of districts |
| Tooltip showed only the state | Could not tell which district a dot was | `hover_name="District"` |
| Two nearly identical map blocks | Duplicate code | One block for both cases |
| No handling of NaN or negative sizes | Possible crashes | `fillna(0).clip(lower=0)` |

## 10. Known limitations and checks

- **Percentage rules are simple.** Columns with "Household" in the name are divided by households, and everything else by population. Not every one of the 100+ columns has been checked against this rule, so spot-check any that look odd. Some columns (for example household-size or latrine-type columns) might be better handled differently.
- **Possible crash:** if every value of the primary parameter is missing for a state, `idxmax()` raises an error. Protect against it by replacing the "Highest district" lines with:

  ```python
  if view["_p"].notna().any():
      top = view.loc[view["_p"].idxmax()]
      c3.metric("Highest district", top["District"], f"{top['_p']:,.2f}", delta_color="off")
  else:
      c3.metric("Highest district", "n/a")
  ```
- **Correlation is not causation.** A high correlation only says two values move together.
- **Bubbles are points, not boundaries.** The CSV has one coordinate per district, so the map shows points rather than district shapes.
- **Map tiles need internet.** The background map is loaded online.

## 11. Troubleshooting

| Problem | Likely cause and fix |
|---|---|
| `FileNotFoundError: india.csv` | Run `streamlit run app.py` from the folder that contains `india.csv` |
| `AttributeError: ... has no attribute 'scatter_map'` | Plotly is too old. Run `pip install -U plotly` (5.24+ needed) |
| `AttributeError: ... 'toggle'` | Streamlit is too old. Run `pip install -U streamlit` (1.26+ needed) |
| `streamlit: command not found` | Activate your virtual environment, or run `python -m streamlit run app.py` |
| Map background is blank | Check your internet connection, or try another "Map style" |
| Bubbles look tiny or huge | Switch the % share toggle, or try a different primary parameter |

## 12. Ideas for next steps

1. **Group the metrics into categories** (Education, Amenities, Religion, Workers) so the dropdowns are easier to navigate.
2. **Compare two states** side by side in a new tab.
3. **Choropleth map:** colour whole district shapes instead of drawing bubbles. This needs a district-boundary GeoJSON file.
4. **Search box** to find a district by name.
5. **Deploy the app** for free on Streamlit Community Cloud by pushing the project to GitHub (keep `requirements.txt` in the repo root).

## 13. Glossary

| Term | Meaning |
|---|---|
| **DataFrame** | A table of data in pandas, with rows and named columns |
| **Series** | One column of a DataFrame |
| **Widget** | An interactive control such as a dropdown, slider or toggle |
| **Sidebar** | The left-hand panel that holds the controls |
| **Cache** | Remembering a result so it does not have to be recomputed |
| **Decorator** | A line starting with `@` placed above a function to change how it behaves |
| **Normalise** | Convert raw counts to a percentage so different-sized districts can be compared fairly |
| **NaN** | "Not a number", pandas' marker for a missing value |
| **Correlation** | A number from -1 to +1 showing how strongly two values move together |
| **f-string** | A string that starts with `f` and lets you put values inside `{}` |
| **Unpacking** | Receiving a function's two returned values into two separate variables |
| **Latitude / Longitude** | A location's north-south and east-west position on Earth |
