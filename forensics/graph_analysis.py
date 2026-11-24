"""
On-Chain Graph Analytics & Sybil Airdrop Clustering using NetworkX and DuckDB.
"""
import os
import json
import duckdb
import networkx as nx
import numpy as np

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "web3_forensics.duckdb")
OUT_PATH = os.path.join(BASE_DIR, "forensics", "graph_metrics.json")

def analyze_onchain_graph():
    print("🕸️ Construindo Grafo Direcionado de Transações com NetworkX...")
    con = duckdb.connect(DB_PATH)
    
    # Load transactions
    tx_df = con.execute("""
        SELECT from_address, to_address, value_native, gas_used, tx_type, is_sybil_farming, chain
        FROM transactions
    """).df()
    
    # Build Directed Graph
    G = nx.DiGraph()
    for _, row in tx_df.iterrows():
        src = row["from_address"]
        dst = row["to_address"]
        weight = float(row["value_native"])
        gas = int(row["gas_used"])
        if G.has_edge(src, dst):
            G[src][dst]["weight"] += weight
            G[src][dst]["tx_count"] += 1
            G[src][dst]["total_gas"] += gas
        else:
            G.add_edge(src, dst, weight=weight, tx_count=1, total_gas=gas)

    nodes_count = G.number_of_nodes()
    edges_count = G.number_of_edges()
    print(f"📊 Grafo construído: {nodes_count:,} Carteiras | {edges_count:,} Arestas de Interação")

    # Compute Centrality & PageRank
    print("⚡ Calculando PageRank e Centralidade dos Hubs...")
    pagerank = nx.pagerank(G, max_iter=100, alpha=0.85)
    in_degrees = dict(G.in_degree())
    out_degrees = dict(G.out_degree())

    # Top Hubs (DEXs, Bridges, Staking Hubs)
    top_hubs = sorted(pagerank.items(), key=lambda x: x[1], reverse=True)[:10]
    
    routers_meta = con.execute("SELECT address, label, category FROM routers").df().set_index("address").to_dict(orient="index")

    hubs_data = []
    for addr, score in top_hubs:
        meta = routers_meta.get(addr, {"label": "Wallet Hub Desconhecido", "category": "Wallet / Contrato"})
        hubs_data.append({
            "address": addr,
            "label": meta["label"],
            "category": meta["category"],
            "pagerank_score": round(float(score) * 100, 4),
            "in_degree": in_degrees.get(addr, 0),
            "out_degree": out_degrees.get(addr, 0)
        })

    # Sybil / Airdrop Farm Detection
    print("🕵️ Detectando Clusters de Airdrop Farming & Padrões Sybil...")
    sybil_query = con.execute("""
        SELECT from_address, count(*) as tx_count, avg(gas_used) as avg_gas, avg(value_native) as avg_val,
               sum(is_sybil_farming) as sybil_signals
        FROM transactions
        GROUP BY from_address
        HAVING sybil_signals > 0
        ORDER BY tx_count DESC
    """).df()

    sybil_clusters = []
    for _, row in sybil_query.head(15).iterrows():
        sybil_clusters.append({
            "wallet": row["from_address"],
            "tx_count": int(row["tx_count"]),
            "avg_gas": round(float(row["avg_gas"]), 0),
            "avg_value": round(float(row["avg_val"]), 6),
            "threat_score": "CRITICAL (Airdrop Ring Sybil)" if row["sybil_signals"] >= 5 else "HIGH (Coordinated Micro-tx)"
        })

    # Gas Anomaly Analysis by Chain
    gas_anomalies = con.execute("""
        SELECT chain, count(*) as total_anomalies, round(avg(gas_used), 0) as avg_anomaly_gas,
               round(avg(value_native), 4) as avg_anomaly_val
        FROM transactions
        WHERE anomaly_flag = 1
        GROUP BY chain
        ORDER BY total_anomalies DESC
    """).df().to_dict(orient="records")

    con.close()

    metrics = {
        "graph": {
            "total_nodes": nodes_count,
            "total_edges": edges_count,
            "top_hubs": hubs_data,
        },
        "sybil_detection": {
            "identified_farming_rings": len(sybil_query),
            "top_flagged_wallets": sybil_clusters,
        },
        "gas_anomalies": gas_anomalies
    }

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2, ensure_ascii=False)
        
    print(f"💾 Métricas forenses salvas em: {OUT_PATH}")
    return metrics

if __name__ == "__main__":
    analyze_onchain_graph()
