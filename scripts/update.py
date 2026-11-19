#!/usr/bin/env python3
"""Rigenera docs/data/state.json.

Scarica i prezzi di chiusura (Yahoo Finance), simula per ogni AI un portafoglio buy-and-hold
con gli importi di config/allocations.json e calcola le statistiche.

Regole:
- Ogni ordine entra alla prima chiusura disponibile dal giorno di partenza (di norma quella del giorno stesso).
- Prima dell'ingresso l'importo resta liquidità. Un ticker senza prezzi resta liquidità e genera un avviso.
- Prezzi "adjusted": il rendimento include i dividendi reinvestiti.
- Titoli in USD convertiti in euro con il cambio EUR/USD della stessa data. Altre valute: escluse con avviso.
- Nessun ribilanciamento, nessuna commissione né tassa.
"""
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config" / "allocations.json"
OUT = ROOT / "docs" / "data" / "state.json"
FX = "EURUSD=X"
EUR_SUFFIX = (".MI", ".DE", ".AS", ".PA", ".MC", ".BR", ".LS", ".HE", ".VI", ".IR")


def currency_of(ticker):
    """Valuta di quotazione: da Yahoo, con ripiego sul suffisso del ticker."""
    try:
        import yfinance as yf
        cur = yf.Ticker(ticker).fast_info.get("currency")
        if cur:
            return str(cur)
    except Exception:
        pass
    return "EUR" if ticker.upper().endswith(EUR_SUFFIX) else "USD"


def download_close(tickers, start):
    """DataFrame di chiusure adjusted, una colonna per ticker (più il cambio), indice = data."""
    import yfinance as yf
    df = yf.download(sorted(set(tickers) | {FX}), start=start, auto_adjust=True,
                     progress=False, group_by="column", threads=True)
    close = df["Close"]
    if isinstance(close, pd.Series):
        close = close.to_frame()
    close.index = pd.to_datetime(close.index).tz_localize(None).normalize()
    return close


def max_drawdown(values):
    peak, mdd = -math.inf, 0.0
    for v in values:
        peak = max(peak, v)
        mdd = min(mdd, v / peak - 1)
    return mdd


def build_state(cfg, close, currencies, now):
    start = pd.Timestamp(cfg["start_date"])
    budget = float(cfg["budget_eur"])
    warnings = []

    for ai in cfg["ais"]:
        total = sum(o["amount_eur"] for o in ai["orders"]) + ai["cash_eur"]
        if abs(total - budget) > 0.01:
            raise SystemExit(f"{ai['name']}: la somma degli importi è {total}, dovrebbe essere {budget}")

    meta = [{"id": a["id"], "name": a["name"], "maker": a["maker"], "slot": a["slot"]} for a in cfg["ais"]]
    base = {"updated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "start_date": cfg["start_date"],
            "budget_eur": budget, "meta": meta, "warnings": warnings}

    close = close.loc[close.index >= start].copy()
    # Prima della chiusura USA (21:00 UTC) la riga di oggi può essere un prezzo parziale: la scarto.
    if (now.hour, now.minute) < (21, 30):
        close = close.loc[close.index.date != now.date()]
    if close.empty or FX not in close or close[FX].dropna().empty:
        return {**base, "pending": True, "dates": [], "ais": []}

    close = close.sort_index()
    fx = close[FX].ffill()
    prices = {}
    for t in sorted({o["ticker"] for a in cfg["ais"] for o in a["orders"]}):
        if t not in close or close[t].dropna().empty:
            warnings.append(f"{t}: nessun prezzo trovato, l'importo resta in liquidità.")
            continue
        cur = currencies.get(t, "EUR").upper()
        s = close[t].ffill()
        if cur == "EUR":
            prices[t] = s
        elif cur == "USD":
            prices[t] = s / fx
        else:
            warnings.append(f"{t}: valuta {cur} non gestita, l'importo resta in liquidità.")
    idx = close.index
    ais_out = []
    for ai in cfg["ais"]:
        legs = []
        for o in ai["orders"]:
            t, amount = o["ticker"], float(o["amount_eur"])
            p = prices.get(t)
            if p is None or p.dropna().empty:
                legs.append({"t": t, "amount": amount, "why": o.get("why", ""), "filled": False})
                continue
            fill_date = p.first_valid_index()
            p0 = float(p[fill_date])
            legs.append({"t": t, "amount": amount, "why": o.get("why", ""), "filled": True,
                         "fill_date": fill_date, "p0": p0, "qty": amount / p0, "p": p})
            if fill_date != start:
                warnings.append(f"{t} ({ai['name']}): ingresso il {fill_date.date()} e non il {start.date()}, per mancanza di prezzi.")
        series = pd.Series(float(ai["cash_eur"]), index=idx)
        for g in legs:
            if g["filled"]:
                series = series + pd.Series([g["qty"] * g["p"][d] if d >= g["fill_date"] else g["amount"] for d in idx], index=idx)
            else:
                series = series + g["amount"]
        vals = [float(v) for v in series]
        value = vals[-1]
        rets = [vals[i] / vals[i - 1] - 1 for i in range(1, len(vals))]
        vol = 0.0
        if len(rets) > 1:
            m = sum(rets) / len(rets)
            vol = math.sqrt(sum((r - m) ** 2 for r in rets) / (len(rets) - 1))
        positions, idle = [], float(ai["cash_eur"])
        for g in legs:
            if not g["filled"]:
                idle += g["amount"]
                continue
            last = float(g["p"].iloc[-1])
            val = g["qty"] * last
            positions.append({"ticker": g["t"], "qty": g["qty"], "avg": g["p0"], "last": last, "value": val,
                              "pl": val - g["amount"], "plp": last / g["p0"] - 1, "weight": val / value,
                              "fill_date": str(g["fill_date"].date()), "why": g["why"]})
        positions.sort(key=lambda x: -x["value"])
        unfilled = [{"ticker": g["t"], "amount": g["amount"]} for g in legs if not g["filled"]]
        ais_out.append({
            "id": ai["id"], "series": [round(v, 4) for v in vals], "value": value, "ret": value / budget - 1,
            "pl": value - budget, "cash": idle, "mdd": max_drawdown(vals), "vol": vol, "positions": positions,
            "unfilled": unfilled,
            "best": max(positions, key=lambda x: x["plp"])["ticker"] if positions else None,
            "worst": min(positions, key=lambda x: x["plp"])["ticker"] if positions else None,
        })
    return {**base, "pending": False, "last_date": str(idx[-1].date()),
            "dates": [str(d.date()) for d in idx], "ais": ais_out}


def main():
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    tickers = sorted({o["ticker"] for a in cfg["ais"] for o in a["orders"]})
    now = datetime.now(timezone.utc)
    try:
        close = download_close(tickers, cfg["start_date"])
    except Exception as e:
        print("Download fallito:", e, file=sys.stderr)
        sys.exit(1)
    currencies = {t: currency_of(t) for t in tickers}
    state = build_state(cfg, close, currencies, now)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(state, ensure_ascii=False, allow_nan=False, indent=1), encoding="utf-8")
    print("state.json scritto:", "in attesa dei prezzi" if state["pending"] else f"{len(state['dates'])} giorni, ultimo {state['last_date']}")
    for w in state["warnings"]:
        print("AVVISO:", w)


if __name__ == "__main__":
    main()
