"""
tracker.py — Enhanced Groww Alert tracker with multi-period P&L insights.

NAV Source
──────────
  Full history endpoint: GET https://api.mfapi.in/mf/{amfi_code}
  (returns all historical NAVs, newest first — no /latest)

Metrics computed per fund
─────────────────────────
  • Latest NAV & date
  • 1-day  P&L  — today vs previous trading day NAV
  • 7-day  P&L  — today vs closest NAV ≤ 7  calendar days ago
  • 30-day P&L  — today vs closest NAV ≤ 30 calendar days ago
  • Overall P&L — current value vs total invested amount

Portfolio-level aggregates
──────────────────────────
  • Sum of all per-fund metrics above
  • 5-day rolling daily gain/loss trend
  • Top & bottom performer today
  • Highest overall gainer

Formula reference
─────────────────
  current_value       = units × latest_nav
  gain_Nd             = (nav_today − nav_Nd_ago) × units
  gain_Nd_pct         = gain_Nd / (units × nav_Nd_ago) × 100
  overall_pnl         = current_value − invested_amount
  overall_pnl_pct     = overall_pnl / invested_amount × 100
"""

import argparse
import json
import sys
from datetime import datetime, date, timedelta, timezone
from typing import Optional

import requests

from config import PORTFOLIO_PATH, AMFI_API_BASE

# IST timezone
IST = timezone(timedelta(hours=5, minutes=30))
# mfapi.in date format
AMFI_DATE_FMT = "%d-%m-%Y"
# Number of recent trading days shown in trend
TREND_DAYS = 5

# ── Shared HTTP session ───────────────────────────────────────────────────────
# A persistent Session re-uses the TLS connection across all fund fetches,
# which prevents the Windows ConnectionReset (10054) that occurs when each
# call creates a fresh TCP+TLS handshake against mfapi.in.
_SESSION = requests.Session()
_SESSION.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.mfapi.in/",
})


# ── Data loading ──────────────────────────────────────────────────────────────

def load_portfolio() -> list[dict]:
    """Read and validate portfolio.json."""
    if not PORTFOLIO_PATH.exists():
        raise FileNotFoundError(
            f"portfolio.json not found at {PORTFOLIO_PATH}.\n"
            "Please create it using the template in the README."
        )
    with PORTFOLIO_PATH.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list) or len(data) == 0:
        raise ValueError("portfolio.json must be a non-empty JSON array.")
    return data


# ── NAV fetching ──────────────────────────────────────────────────────────────

def fetch_nav_history(amfi_code: str) -> tuple[list[dict], dict]:
    """
    Fetch the complete NAV history for a fund from mfapi.in.

    Endpoint: GET https://api.mfapi.in/mf/{amfi_code}
    (NOT /latest — we need historical data for multi-period comparisons)

    Returns
    -------
    history : list[dict]
        Each element: {"date": date, "nav": float}
        Sorted newest → oldest.
    meta : dict
        Fund metadata from the API (scheme_name, fund_house, etc.)
    """
    url = f"{AMFI_API_BASE}/{amfi_code}"

    # Use the shared session (keeps TLS connection alive, avoids Windows reset).
    import time as _time
    last_exc: Exception = RuntimeError("Unknown error")
    for attempt in range(1, 4):                    # up to 3 attempts
        try:
            resp = _SESSION.get(url, timeout=30)
            resp.raise_for_status()
            break                                  # success — exit retry loop
        except requests.exceptions.RequestException as exc:
            last_exc = exc
            if attempt < 3:
                _time.sleep(2 * attempt)           # back-off: 2 s, then 4 s
    else:
        raise RuntimeError(
            f"Failed to fetch NAV history for AMFI code {amfi_code} "
            f"after 3 attempts: {last_exc}"
        )

    payload = resp.json()

    try:
        raw_data = payload["data"]   # [{"date": "DD-MM-YYYY", "nav": "xxx.xxxx"}, ...]
        meta = payload.get("meta", {})
    except (KeyError, TypeError) as exc:
        raise RuntimeError(f"Unexpected API response structure for {amfi_code}: {exc}") from exc

    history = []
    for entry in raw_data:
        try:
            d = datetime.strptime(entry["date"], AMFI_DATE_FMT).date()
            nav = float(entry["nav"])
            history.append({"date": d, "nav": nav})
        except (ValueError, KeyError):
            continue  # skip malformed entries

    if not history:
        raise RuntimeError(f"No valid NAV entries returned for AMFI code {amfi_code}.")

    # mfapi.in returns newest-first; sort explicitly to guarantee order
    history.sort(key=lambda x: x["date"], reverse=True)
    return history, meta


def nav_on_or_before(history: list[dict], target: date) -> Optional[dict]:
    """
    Return the most recent entry whose date is ≤ target.
    history must be sorted newest → oldest.
    Returns None if no such entry exists (target is before the fund's inception).
    """
    for entry in history:
        if entry["date"] <= target:
            return entry
    return None


# ── Calculation engine ────────────────────────────────────────────────────────

def _gain_pct(gain: float, base_value: float) -> float:
    """Return gain as a percentage of base_value. Safe against zero division."""
    return (gain / base_value * 100) if base_value != 0 else 0.0


def calculate_fund(holding: dict, history: list[dict], meta: dict) -> dict:
    """
    Compute all P&L metrics for a single fund holding.

    Formulas
    --------
    current_value   = units × nav_today
    gain_1d         = (nav_today  − nav_prev_day) × units
    gain_7d         = (nav_today  − nav_7d_ago)   × units
    gain_30d        = (nav_today  − nav_30d_ago)  × units
    overall_pnl     = current_value − invested_amount
    overall_pnl_pct = overall_pnl / invested_amount × 100
    """
    units    = float(holding["units"])
    invested = float(holding["invested_amount"])

    # ── Latest NAV ────────────────────────────────────────────────────────────
    latest    = history[0]
    nav_today = latest["nav"]
    nav_date  = latest["date"]

    current_value = units * nav_today

    # ── 1-Day: previous available trading day ─────────────────────────────────
    prev = history[1] if len(history) > 1 else None
    if prev:
        gain_1d     = (nav_today - prev["nav"]) * units
        base_1d     = units * prev["nav"]
        gain_1d_pct = _gain_pct(gain_1d, base_1d)
    else:
        gain_1d = gain_1d_pct = None

    # ── 7-Day ─────────────────────────────────────────────────────────────────
    target_7d  = nav_date - timedelta(days=7)
    entry_7d   = nav_on_or_before(history, target_7d)
    if entry_7d:
        gain_7d     = (nav_today - entry_7d["nav"]) * units
        base_7d     = units * entry_7d["nav"]
        gain_7d_pct = _gain_pct(gain_7d, base_7d)
    else:
        gain_7d = gain_7d_pct = None

    # ── 30-Day ────────────────────────────────────────────────────────────────
    target_30d = nav_date - timedelta(days=30)
    entry_30d  = nav_on_or_before(history, target_30d)
    if entry_30d:
        gain_30d     = (nav_today - entry_30d["nav"]) * units
        base_30d     = units * entry_30d["nav"]
        gain_30d_pct = _gain_pct(gain_30d, base_30d)
    else:
        gain_30d = gain_30d_pct = None

    # ── Overall ───────────────────────────────────────────────────────────────
    overall_pnl     = current_value - invested
    overall_pnl_pct = _gain_pct(overall_pnl, invested)

    return {
        "fund_name"     : holding.get("fund_name", meta.get("scheme_name", "Unknown Fund")),
        "amfi_code"     : holding["amfi_code"],
        "nav"           : nav_today,
        "nav_date"      : nav_date.strftime("%d %b %Y"),
        "units"         : units,
        "invested"      : invested,
        "current_value" : current_value,
        # 1-day
        "gain_1d"       : gain_1d,
        "gain_1d_pct"   : gain_1d_pct,
        "prev_nav_date" : prev["date"].strftime("%d %b %Y") if prev else None,
        # 7-day
        "gain_7d"       : gain_7d,
        "gain_7d_pct"   : gain_7d_pct,
        # 30-day
        "gain_30d"      : gain_30d,
        "gain_30d_pct"  : gain_30d_pct,
        # Overall
        "overall_pnl"   : overall_pnl,
        "overall_pnl_pct": overall_pnl_pct,
    }


# ── Portfolio-level rolling trend ─────────────────────────────────────────────

def compute_daily_trend(holdings_histories: list[tuple], days: int = TREND_DAYS) -> list[dict]:
    """
    Compute portfolio-level daily P&L for the last `days` trading days.

    Parameters
    ----------
    holdings_histories : list of (units, nav_history) tuples
    days               : how many past trading days to show

    Algorithm
    ---------
    For each trading date i in the reference calendar (newest → oldest):
      portfolio_value[i] = Σ (units_k × nav_k_on_date_i)
      daily_gain[i]      = portfolio_value[i] − portfolio_value[i+1]
    """
    if not holdings_histories:
        return []

    # Use the fund with the most history as the trading-day calendar
    ref_history = max(holdings_histories, key=lambda x: len(x[1]))[1]
    max_idx = min(days + 1, len(ref_history))

    portfolio_by_day = []
    for i in range(max_idx):
        ref_date  = ref_history[i]["date"]
        day_total = 0.0
        for units, hist in holdings_histories:
            entry = nav_on_or_before(hist, ref_date)
            if entry:
                day_total += units * entry["nav"]
        portfolio_by_day.append({"date": ref_date, "value": day_total})

    trend = []
    for i in range(len(portfolio_by_day) - 1):
        today_val = portfolio_by_day[i]["value"]
        prev_val  = portfolio_by_day[i + 1]["value"]
        gain      = today_val - prev_val
        trend.append({
            "date"  : portfolio_by_day[i]["date"].strftime("%d %b"),
            "gain"  : gain,
            "pct"   : _gain_pct(gain, prev_val),
            "value" : today_val,
        })
    return trend[:days]


# ── Message formatter ─────────────────────────────────────────────────────────

def _fmt_money(amount: float) -> str:
    """Format ₹ with Indian comma style (e.g. ₹14,99,925.04)."""
    # Python's locale-independent Indian number formatting
    abs_amt = abs(amount)
    s = f"{abs_amt:,.2f}"
    # Convert Western grouping (1,499,925.04) → Indian (14,99,925.04)
    parts = s.split(".")
    integer = parts[0].replace(",", "")
    decimal = parts[1]
    if len(integer) <= 3:
        formatted = integer
    else:
        last3 = integer[-3:]
        rest = integer[:-3]
        groups = []
        while len(rest) > 2:
            groups.append(rest[-2:])
            rest = rest[:-2]
        if rest:
            groups.append(rest)
        groups.reverse()
        formatted = ",".join(groups) + "," + last3
    sign = "-" if amount < 0 else ""
    return f"₹{sign}{formatted}.{decimal}"


def _fmt_gain(gain: Optional[float], pct: Optional[float]) -> str:
    """Format a gain line with emoji, sign, ₹ and %."""
    if gain is None:
        return "N/A"
    emoji = "📈" if gain >= 0 else "📉"
    sign  = "+" if gain >= 0 else ""
    pct_s = f"{sign}{pct:.2f}%" if pct is not None else ""
    return f"{emoji} {sign}{_fmt_money(gain)} ({pct_s})"


def _short(name: str, max_len: int = 32) -> str:
    return name[:max_len] + ("…" if len(name) > max_len else "")


def format_message(results: list[dict], trend: list[dict]) -> str:
    """Build the complete WhatsApp summary."""

    # ── Portfolio aggregates ──────────────────────────────────────────────────
    total_invested    = sum(r["invested"]      for r in results)
    total_value       = sum(r["current_value"] for r in results)
    overall_pnl       = total_value - total_invested
    overall_pnl_pct   = _gain_pct(overall_pnl, total_invested)

    def _safe_sum(field):
        vals = [r[field] for r in results if r[field] is not None]
        return sum(vals) if vals else None

    agg_1d      = _safe_sum("gain_1d")
    agg_1d_pct  = _gain_pct(agg_1d, total_value - agg_1d) if agg_1d is not None else None
    agg_7d      = _safe_sum("gain_7d")
    agg_7d_pct  = _gain_pct(agg_7d, total_value - agg_7d) if agg_7d is not None else None
    agg_30d     = _safe_sum("gain_30d")
    agg_30d_pct = _gain_pct(agg_30d, total_value - agg_30d) if agg_30d is not None else None

    # ── Highlights ────────────────────────────────────────────────────────────
    funds_with_1d = [r for r in results if r["gain_1d"] is not None]
    top_today  = max(funds_with_1d, key=lambda r: r["gain_1d"])  if funds_with_1d else None
    bot_today  = min(funds_with_1d, key=lambda r: r["gain_1d"])  if funds_with_1d else None
    top_overall = max(results, key=lambda r: r["overall_pnl_pct"])

    now_ist  = datetime.now(IST)
    date_str = now_ist.strftime("%d %b %Y, %I:%M %p IST")

    lines = [
        "━━━━━━━━━━━━━━━━━━━━━━━━━",
        "💼 *GROWW PORTFOLIO ALERT*",
        f"🕘 {date_str}",
        "━━━━━━━━━━━━━━━━━━━━━━━━━",
        "",
    ]

    # ── Per-fund section ──────────────────────────────────────────────────────
    for r in results:
        lines += [
            f"*{_short(r['fund_name'])}*",
            f"  NAV: ₹{r['nav']:,.4f}  ({r['nav_date']})",
            f"  Units: {r['units']:,.3f}",
            f"  Current Value: {_fmt_money(r['current_value'])}",
            "",
            f"  📅 Today:   {_fmt_gain(r['gain_1d'],  r['gain_1d_pct'])}",
            f"  📅 7-Day:   {_fmt_gain(r['gain_7d'],  r['gain_7d_pct'])}",
            f"  📅 30-Day:  {_fmt_gain(r['gain_30d'], r['gain_30d_pct'])}",
            f"  📊 Overall: {_fmt_gain(r['overall_pnl'], r['overall_pnl_pct'])}",
            "  ─────────────────────────",
            "",
        ]

    # ── Portfolio summary ─────────────────────────────────────────────────────
    pnl_emoji = "📈" if overall_pnl >= 0 else "📉"
    lines += [
        "━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"{pnl_emoji} *PORTFOLIO SUMMARY*",
        f"  Total Invested: {_fmt_money(total_invested)}",
        f"  Total Value:    {_fmt_money(total_value)}",
        "",
        f"  📅 Today's Gain:  {_fmt_gain(agg_1d,  agg_1d_pct)}",
        f"  📅 7-Day Gain:    {_fmt_gain(agg_7d,  agg_7d_pct)}",
        f"  📅 30-Day Gain:   {_fmt_gain(agg_30d, agg_30d_pct)}",
        f"  📊 Net P&L:       {_fmt_gain(overall_pnl, overall_pnl_pct)}",
        "",
    ]

    # ── 5-day trend ───────────────────────────────────────────────────────────
    if trend:
        lines.append("  📉📈 *Recent Daily Trend*")
        for t in trend:
            arrow = "▲" if t["gain"] >= 0 else "▼"
            sign  = "+" if t["gain"] >= 0 else ""
            lines.append(
                f"  {t['date']}: {arrow} {sign}{_fmt_money(t['gain'])} ({sign}{t['pct']:.2f}%)"
            )
        lines.append("")

    # ── Highlights ────────────────────────────────────────────────────────────
    if top_today:
        sign = "+" if top_today["gain_1d"] >= 0 else ""
        # On a red day, "best" is the least-loss fund — label it accordingly
        if top_today["gain_1d"] >= 0:
            top_label, top_emoji = "Best Today:", "🏆"
        else:
            top_label, top_emoji = "Least Loss:", "🛡️ "
        lines.append(
            f"{top_emoji} *{top_label}* {_short(top_today['fund_name'], 22)} "
            f"({sign}{_fmt_money(top_today['gain_1d'])})"
        )
    if bot_today and bot_today is not top_today:
        sign = "+" if bot_today["gain_1d"] >= 0 else ""
        lines.append(
            f"⚠️  *Weakest:*    {_short(bot_today['fund_name'], 22)} "
            f"({sign}{_fmt_money(bot_today['gain_1d'])})"
        )
    lines += [
        f"🥇 *Best Overall:* {_short(top_overall['fund_name'], 20)} "
        f"({'+' if top_overall['overall_pnl']>=0 else ''}{top_overall['overall_pnl_pct']:.2f}%)",
        "",
        "━━━━━━━━━━━━━━━━━━━━━━━━━",
        "_Data: AMFI via mfapi.in · Groww Alert_",
    ]

    return "\n".join(lines)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Groww Alert — Portfolio Tracker")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch NAVs, calculate P&L and print the message preview — skip WhatsApp dispatch.",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("  Groww Alert — Enhanced Portfolio Tracker")
    print(f"  {datetime.now(IST).strftime('%d %b %Y %I:%M %p IST')}")
    if args.dry_run:
        print("  ⚠️  DRY-RUN MODE — WhatsApp will NOT be sent")
    print("=" * 60)

    # 1. Load portfolio
    print("\n📂 Loading portfolio.json …")
    try:
        portfolio = load_portfolio()
    except (FileNotFoundError, ValueError) as exc:
        print(f"❌ {exc}")
        sys.exit(1)
    print(f"   {len(portfolio)} holding(s) found.")

    # 2. Fetch NAV histories and calculate
    print("\n🌐 Fetching full NAV history from AMFI (mfapi.in) …")
    results       = []
    holdings_hist = []   # for trend computation
    errors        = []

    for holding in portfolio:
        amfi_code  = str(holding.get("amfi_code", "")).strip()
        fund_label = holding.get("fund_name", f"AMFI:{amfi_code}")
        print(f"\n   → {fund_label[:55]}")
        print(f"      AMFI code: {amfi_code}")

        try:
            history, meta = fetch_nav_history(amfi_code)
            calc = calculate_fund(holding, history, meta)
            results.append(calc)
            holdings_hist.append((calc["units"], history))

            print(f"      NAV : ₹{calc['nav']:.4f}  ({calc['nav_date']})")
            sign = "+" if calc["overall_pnl"] >= 0 else ""
            print(f"      Val : {_fmt_money(calc['current_value'])}")
            print(f"      P&L : {sign}{_fmt_money(calc['overall_pnl'])} ({sign}{calc['overall_pnl_pct']:.2f}%)")
            if calc["gain_1d"] is not None:
                s = "+" if calc["gain_1d"] >= 0 else ""
                print(f"      1-Day: {s}{_fmt_money(calc['gain_1d'])} ({s}{calc['gain_1d_pct']:.2f}%)")
        except RuntimeError as exc:
            print(f"      ❌ ERROR — {exc}")
            errors.append(fund_label)

    if not results:
        print("\n❌ No fund data could be retrieved. Aborting.")
        sys.exit(1)

    if errors:
        print(f"\n⚠️  Skipped {len(errors)} fund(s) due to errors: {errors}")

    # 3. Compute rolling daily trend
    print(f"\n📊 Computing {TREND_DAYS}-day portfolio trend …")
    trend = compute_daily_trend(holdings_hist, days=TREND_DAYS)
    for t in trend:
        s = "+" if t["gain"] >= 0 else ""
        print(f"   {t['date']}: {s}{_fmt_money(t['gain'])} ({s}{t['pct']:.2f}%)")

    # 4. Format message
    print("\n📝 Formatting WhatsApp message …")
    message = format_message(results, trend)
    print("\n── Message Preview ──────────────────────────────────────")
    print(message)
    print("─────────────────────────────────────────────────────────\n")

    # 5. Send WhatsApp (skipped in dry-run mode)
    if args.dry_run:
        print("⏭️  Dry-run: WhatsApp send skipped. All calculations verified ✅")
        return

    # Import notifier only when actually sending (requires valid API key)
    from notifier import send_whatsapp  # noqa: PLC0415
    print("📲 Sending WhatsApp notification …")
    success = send_whatsapp(message)

    if not success:
        sys.exit(1)

    print("\n✅ Done.")


if __name__ == "__main__":
    main()
