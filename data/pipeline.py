"""
Web3 On-Chain & Gas Forensics Pipeline.
Ingests multi-chain block telemetry, EIP-1559 gas dynamics, and transaction graphs
across Ethereum Sepolia, Monad, 0G Galileo, and Celo into DuckDB.
"""
import os
import duckdb
import numpy as np
import pandas as pd
import time

DB_PATH = os.path.join(os.path.dirname(__file__), "web3_forensics.duckdb")

CHAINS = {
    "Ethereum Sepolia": {"chain_id": 11155111, "base_fee_gwei": 0.05, "gas_limit": 30000000, "tps_avg": 18.5, "symbol": "ETH"},
    "Monad Testnet": {"chain_id": 10143, "base_fee_gwei": 0.001, "gas_limit": 50000000, "tps_avg": 850.0, "symbol": "MON"},
    "0G Galileo": {"chain_id": 16600, "base_fee_gwei": 0.002, "gas_limit": 40000000, "tps_avg": 420.0, "symbol": "0G"},
    "Celo Mainnet": {"chain_id": 42220, "base_fee_gwei": 0.008, "gas_limit": 20000000, "tps_avg": 45.0, "symbol": "CELO"},
}

KNOWN_ROUTERS = [
    ("0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D", "Uniswap V2 Router", "DEX"),
    ("0xE592427A0AEce92De3Edee1F18E0157C05861564", "Uniswap V3 Router", "DEX"),
    ("0x1111111254fb6c44bac0bed2854e76f90643097d", "1inch Aggregator", "DEX"),
    ("0xd9e1cE17f2641f24aE83637ab66a2cca9C378B9F", "SushiSwap Router", "DEX"),
    ("0x401F6c983eA34274ec46f84D70b31C151321188b", "Polygon/Sepolia Bridge Gateway", "Bridge"),
    ("0x0000000000000000000000000000000000001010", "ZeroG Staking Validator Hub", "Staking"),
]

def generate_onchain_telemetry(num_blocks=1200, num_txs=25000):
    np.random.seed(42)
    print("⛓️ Gerando telemetria on-chain forense para 4 redes blockchain...")
    
    # Generate Blocks
    block_records = []
    chains_list = list(CHAINS.keys())
    
    curr_time = int(time.time()) - (num_blocks * 12)
    
    for b_idx in range(num_blocks):
        chain = chains_list[b_idx % len(chains_list)]
        c_meta = CHAINS[chain]
        block_num = 7000000 + b_idx
        
        gas_limit = c_meta["gas_limit"]
        gas_used = int(gas_limit * np.random.beta(5, 3))
        gas_saturation = round((gas_used / gas_limit) * 100, 2)
        
        # Base fee spike on high saturation
        base_fee = c_meta["base_fee_gwei"] * (1.0 + (gas_saturation / 100.0) ** 2)
        base_fee += np.random.normal(0, base_fee * 0.05)
        base_fee = max(0.0001, round(base_fee, 6))
        
        tx_count = int(np.random.poisson(c_meta["tps_avg"] * 2.0))
        burnt_fee = round((gas_used * base_fee * 1e-9), 6)
        
        block_records.append({
            "chain": chain,
            "chain_id": c_meta["chain_id"],
            "block_number": block_num,
            "timestamp": curr_time + (b_idx * 12),
            "gas_limit": gas_limit,
            "gas_used": gas_used,
            "gas_saturation_pct": gas_saturation,
            "base_fee_gwei": base_fee,
            "tx_count": tx_count,
            "burnt_fees_native": burnt_fee,
            "symbol": c_meta["symbol"]
        })
        
    df_blocks = pd.DataFrame(block_records)
    
    # Generate Transactions & Wallet Interactions
    tx_records = []
    
    # Seed known wallets & sybil rings
    sybil_ring_lead = "0x88F062c3f8510aB7243cE016a2A47883a2Cd4201"
    sybil_wallets = [f"0x{i:04x}a1b2c3d4e5f67890123456789abcdef{i:04x}" for i in range(120)]
    
    normal_wallets = [f"0x{np.random.randint(1000000, 9999999):x}d9e1cE17f2641f24aE83637ab66a2cca9C378B9F"[:42] for _ in range(800)]
    all_known_routers = [r[0] for r in KNOWN_ROUTERS]

    tx_types = ["Native Transfer", "DEX Swap", "NFT Mint", "Bridge Deposit", "Smart Contract Deploy", "Airdrop Claim / Farm"]
    tx_type_weights = [0.35, 0.30, 0.10, 0.10, 0.05, 0.10]

    for t_idx in range(num_txs):
        chain = chains_list[t_idx % len(chains_list)]
        c_meta = CHAINS[chain]
        tx_type = np.random.choice(tx_types, p=tx_type_weights)
        
        # Decide if Sybil ring interaction
        is_sybil = (np.random.rand() < 0.12)
        if is_sybil:
            from_wallet = np.random.choice(sybil_wallets)
            to_wallet = sybil_ring_lead if (np.random.rand() < 0.3) else np.random.choice(all_known_routers)
            gas_used = np.random.randint(21000, 45000)
            value_native = round(float(np.random.uniform(0.0001, 0.005)), 6)
            priority_fee = round(float(np.random.uniform(0.001, 0.01)), 4)
            anomaly_flag = 1
        else:
            from_wallet = np.random.choice(normal_wallets)
            to_wallet = np.random.choice(all_known_routers) if (np.random.rand() < 0.45) else np.random.choice(normal_wallets)
            gas_used = np.random.randint(21000, 350000)
            value_native = round(float(np.random.exponential(0.4)), 4)
            priority_fee = round(float(np.random.uniform(0.01, 0.25)), 4)
            anomaly_flag = int(gas_used > 280000 or value_native > 15.0)

        tx_hash = f"0x{t_idx:08x}{np.random.randint(10000000, 99999999):x}{np.random.randint(10000000, 99999999):x}"[:66]
        base_fee = c_meta["base_fee_gwei"] * np.random.uniform(0.9, 1.4)
        total_gas_fee_native = round((gas_used * (base_fee + priority_fee) * 1e-9), 8)

        tx_records.append({
            "tx_hash": tx_hash,
            "chain": chain,
            "from_address": from_wallet,
            "to_address": to_wallet,
            "tx_type": tx_type,
            "value_native": value_native,
            "gas_used": gas_used,
            "base_fee_gwei": round(base_fee, 6),
            "priority_fee_gwei": round(priority_fee, 4),
            "total_gas_fee_native": total_gas_fee_native,
            "status": "Success" if np.random.rand() > 0.03 else "Reverted",
            "is_sybil_farming": int(is_sybil),
            "anomaly_flag": anomaly_flag,
            "symbol": c_meta["symbol"]
        })

    df_txs = pd.DataFrame(tx_records)

    # Ingest into DuckDB
    con = duckdb.connect(DB_PATH)
    con.execute("DROP TABLE IF EXISTS blocks")
    con.execute("DROP TABLE IF EXISTS transactions")
    con.execute("DROP TABLE IF EXISTS routers")
    
    con.execute("CREATE TABLE blocks AS SELECT * FROM df_blocks")
    con.execute("CREATE TABLE transactions AS SELECT * FROM df_txs")
    
    df_routers = pd.DataFrame(KNOWN_ROUTERS, columns=["address", "label", "category"])
    con.execute("CREATE TABLE routers AS SELECT * FROM df_routers")
    
    b_count = con.execute("SELECT count(*) FROM blocks").fetchone()[0]
    t_count = con.execute("SELECT count(*) FROM transactions").fetchone()[0]
    con.close()
    
    print(f"✅ DuckDB Web3 Forensics criado em: {DB_PATH}")
    print(f"📦 Blocos Indexados: {b_count:,}")
    print(f"⚡ Transações Indexadas: {t_count:,}")
    return df_blocks, df_txs

if __name__ == "__main__":
    generate_onchain_telemetry()
