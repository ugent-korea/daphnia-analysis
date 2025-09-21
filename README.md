<p align="center">
  <img src="app/assets/daphnia.svg" alt="Daphnia" width="200" />
</p>

<h1 align="center">Daphnia Coding Protocol</h1>
<p align="center">
  <a href="https://www.python.org/">
    <img alt="Python" src="https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white">
  </a>
  <a href="https://streamlit.io/">
    <img alt="Streamlit" src="https://img.shields.io/badge/Streamlit-App-FF4B4B?logo=streamlit&logoColor=white">
  </a>
  <a href="https://pandas.pydata.org/">
    <img alt="pandas" src="https://img.shields.io/badge/pandas-Data-150458?logo=pandas&logoColor=white">
  </a>
  <a href="https://docs.sqlalchemy.org/">
    <img alt="SQLAlchemy" src="https://img.shields.io/badge/SQLAlchemy-ORM-D71F00">
  </a>
  <a href="https://www.postgresql.org/">
    <img alt="PostgreSQL (Neon)" src="https://img.shields.io/badge/PostgreSQL-Neon-4169E1?logo=postgresql&logoColor=white">
  </a>
  <a href="https://developers.google.com/sheets/api">
    <img alt="Google Sheets" src="https://img.shields.io/badge/Google%20Sheets-ETL-34A853?logo=googlesheets&logoColor=white">
  </a>
  <a href="https://github.com/features/actions">
    <img alt="GitHub Actions" src="https://img.shields.io/badge/GitHub%20Actions-Scheduler-2088FF?logo=githubactions&logoColor=white">
  </a>
  <a href="https://streamlit.io/cloud">
    <img alt="Hosted on Streamlit Cloud" src="https://img.shields.io/badge/Hosted%20on-Streamlit%20Cloud-FF4B4B?logo=streamlit&logoColor=white">
  </a>
</p>
<p align="center"><sub>by <a href="https://github.com/chaerheeon">@chaerheeon</a></sub></p>

---

## Quick Start
1. [**Open the app.**](https://daphnia-coding-protocol.streamlit.app/) 
   - Check the **Last refresh (KST)** line under the subtitle. **Make sure it's today's date**.
     - Notify the supervisor to update.
   - Any data modified after 12:00 AM of each day will not be accounted for.
2. **Enter a MotherID** in the first box:
   - You can paste a **core** (e.g., `E.1`, `E.1.3`, `A2`, `B.3`) or a **full** ID (e.g., `E.1_0804`, `E.1.3_0912`).
3. **Date suffix** defaults to **today (KST)** as `_MMDD`. 
   - Change it if needed; if left blank, today’s date is applied automatically.
4. Click outside the field (or press Enter) to see:
   - **Suggested Child ID** (with the date suffix),
   - **Discard?** (**Yes** in red or **No**),
   - A short reason explaining the decision.
5. (Optional) Expand **Parent details** and **Existing children** for context.

---

## What You Can Type (Input Normalization)
- The app accepts old and mixed formats and normalizes to dotted **core** form.
- Examples:

  | You type                     | Interpreted core |
  |-----------------------------|------------------|
  | `E1` / `e1` / `E.01`        | `E.1`            |
  | `E1.2` / `E.1.02`           | `E.1.2`          |
  | `E.1_0804`                  | core `E.1`, date `_0804` |
  | `A2` / `A.2`                | `A.2`            |
  | `B3.1_0912`                 | core `B.3.1`, date `_0912` |

- If you enter **core-only** (e.g., `E.1`), the app looks up the **latest** record for that core by numeric date suffix.
- The **Suggested Child ID** always includes a date: your input suffix or (if empty) **today (KST)**.
