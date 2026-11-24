"""
FastAPI Backend for Web3 On-Chain & Gas Forensics.
Serves on-chain telemetry, gas saturation, and Sybil cluster detection.
"""
import os
import json
import duckdb
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "web3_forensics.duckdb")
METRICS_PATH = os.path.join(BASE_DIR, "forensics", "graph_metrics.json")

app = FastAPI(title="Web3 On-Chain & Gas Forensics", version="1.0.0")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "app", "templates"))

# Load precomputed graph metrics
with open(METRICS_PATH, "r", encoding="utf-8") as f:
    graph_metrics = json.load(f)

@app.get("/", response_class=HTMLResponse)
async def serve_home(request: Request):
    con = duckdb.connect(DB_PATH)
    chains_summary = con.execute("""
        SELECT chain, count(*) as tx_count, round(avg(gas_used), 0) as avg_gas,
               round(avg(base_fee_gwei), 4) as avg_base_fee, round(sum(total_gas_fee_native), 4) as total_fees_spent,
               round(sum(is_sybil_farming) * 100.0 / count(*), 1) as sybil_pct
        FROM transactions
        GROUP BY chain
        ORDER BY tx_count DESC
    """).df().to_dict(orient="records")
    con.close()

    return templates.TemplateResponse("index.html", {
        "request": request,
        "chains": chains_summary,
        "metrics": graph_metrics,
    })

@app.get("/api/telemetry")
async def get_telemetry():
    con = duckdb.connect(DB_PATH)
    
    # 1. Blocks time series
    blocks_df = con.execute("""
        SELECT block_number, chain, gas_saturation_pct, base_fee_gwei, tx_count, burnt_fees_native
        FROM blocks
        ORDER BY block_number ASC
        LIMIT 100
    """).df().to_dict(orient="records")

    # 2. Tx types breakdown
    tx_types = con.execute("""
        SELECT tx_type, count(*) as count, round(avg(gas_used), 0) as avg_gas
        FROM transactions
        GROUP BY tx_type
        ORDER BY count DESC
    """).df().to_dict(orient="records")

    con.close()
    return JSONResponse({
        "blocks": blocks_df,
        "tx_types": tx_types,
        "graph": graph_metrics["graph"],
        "sybil": graph_metrics["sybil_detection"],
        "anomalies": graph_metrics["gas_anomalies"]
    })

@app.get("/api/wallet_audit")
async def audit_wallet(address: str):
    addr = address.strip().lower()
    con = duckdb.connect(DB_PATH)
    
    # Check if wallet exists in transactions
    txs = con.execute(f"""
        SELECT tx_hash, chain, to_address, tx_type, value_native, gas_used, status, is_sybil_farming
        FROM transactions
        WHERE lower(from_address) = '{addr}' OR lower(to_address) = '{addr}'
        LIMIT 10
    """).df().to_dict(orient="records")

    total_tx = con.execute(f"SELECT count(*) FROM transactions WHERE lower(from_address) = '{addr}'").fetchone()[0]
    con.close()

    if total_tx == 0:
        # Benchmark score for external/fresh wallets
        return JSONResponse({
            "address": address,
            "status": "Safe / Fresh Wallet",
            "risk_score": 12,
            "category": "Retail On-Chain User",
            "cluster_detected": "Legitimate Standalone",
            "analysis": "Nenhum padrão de automação de airdrop farming ou saturação maliciosa de gás detectado."
        })

    is_sybil = any(t.get("is_sybil_farming") == 1 for t in txs)
    return JSONResponse({
        "address": address,
        "status": "FLAGGED SYBIL" if is_sybil else "Active Node",
        "risk_score": 88 if is_sybil else 24,
        "total_tx": total_tx,
        "category": "Airdrop Ring Bot" if is_sybil else "DeFi Regular Participant",
        "recent_txs": txs
    })

if __name__ == "__main__":
    import uvicorn
    print("🚀 Iniciando Web3 Gas Forensics na porta 8003...")
    uvicorn.run("main:app", host="127.0.0.1", port=8003, reload=False)
