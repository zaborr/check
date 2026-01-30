import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timezone

BASE_URL = "https://api.coingecko.com/api/v3"
VS = "usd"

st.set_page_config(page_title="Crypto Relative Performance", layout="wide")
st.title("📊 Crypto Relative Performance")
st.caption("Comparativa en USD, BTC y ETH con datos horarios (CoinGecko)")

# ---------------- helpers ----------------

def ts(dt):
    return int(dt.replace(tzinfo=timezone.utc).timestamp())

@st.cache_data(ttl=3600)
def get_top_20():
    r = requests.get(
        f"{BASE_URL}/coins/markets",
        params={
            "vs_currency": "usd",
            "order": "market_cap_desc",
            "per_page": 20,
            "page": 1
        },
        timeout=20
    )
    r.raise_for_status()
    return {c["id"]: c["symbol"].upper() for c in r.json()}

@st.cache_data(ttl=3600)
def get_price_at(coin_id, dt):
    r = requests.get(
        f"{BASE_URL}/coins/{coin_id}/market_chart/range",
        params={
            "vs_currency": VS,
            "from": ts(dt) - 1800,
            "to": ts(dt) + 1800
        },
        timeout=20
    )
    r.raise_for_status()

    prices = r.json().get("prices", [])
    if not prices:
        return None

    prices.sort(key=lambda x: abs(x[0] - ts(dt) * 1000))
    return prices[0][1]

# ---------------- UI ----------------

with st.sidebar:
    st.header("⚙️ Parámetros")

    target_coin = st.text_input(
        "Moneda objetivo (CoinGecko ID)",
        value="bitcoin",
        help="Ej: bitcoin, ethereum, solana"
    )

    date1 = st.datetime_input(
        "Fecha / hora inicial (UTC)",
        value=datetime(2024, 12, 1, 12, 0)
    )

    use_now = st.checkbox("Usar ahora como fecha final", value=True)

    if use_now:
        date2 = datetime.utcnow()
    else:
        date2 = st.datetime_input(
            "Fecha / hora final (UTC)",
            value=datetime.utcnow()
        )

    run = st.button("Calcular")

# ---------------- logic ----------------

if run:
    with st.spinner("Consultando CoinGecko y haciendo cuentas incómodas..."):
        coins = get_top_20()
        coins[target_coin] = target_coin.upper()

        prices_1 = {}
        prices_2 = {}
        skipped = []

        for cid in coins:
            p1 = get_price_at(cid, date1)
            p2 = get_price_at(cid, date2)

            if p1 is None or p2 is None:
                skipped.append(cid)
                continue

            prices_1[cid] = p1
            prices_2[cid] = p2

        # Protección crítica
        if "bitcoin" not in prices_1 or "ethereum" not in prices_1:
            st.error("No hay datos suficientes para BTC o ETH en esas fechas.")
            st.stop()

        btc1, btc2 = prices_1["bitcoin"], prices_2["bitcoin"]
        eth1, eth2 = prices_1["ethereum"], prices_2["ethereum"]

        rows = []
        for cid, sym in coins.items():
            if cid not in prices_1:
                continue

            p1, p2 = prices_1[cid], prices_2[cid]

            rows.append({
                "Moneda": sym,

                "USD inicio": round(p1, 4),
                "USD final": round(p2, 4),
                "% USD": round((p2 - p1) / p1 * 100, 2),

                "BTC inicio": round(p1 / btc1, 8),
                "BTC final": round(p2 / btc2, 8),
                "% BTC": round(((p2 / btc2) - (p1 / btc1)) / (p1 / btc1) * 100, 2),

                "ETH inicio": round(p1 / eth1, 8),
                "ETH final": round(p2 / eth2, 8),
                "% ETH": round(((p2 / eth2) - (p1 / eth1)) / (p1 / eth1) * 100, 2),
            })

        df = pd.DataFrame(rows).sort_values("% USD")

        st.success("Cálculo terminado. Los números ya pueden juzgarte.")
        st.dataframe(df, use_container_width=True)

        if skipped:
            st.warning(
                f"Monedas omitidas por falta de datos horarios: "
                f"{', '.join(skipped)}"
            )

        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇️ Descargar CSV",
            csv,
            "crypto_relative.csv",
            "text/csv"
        )
