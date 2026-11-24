@echo off
chcp 65001 > nul
title Web3 On-Chain & Gas Forensics - 2026 Live
color 0B

echo ==============================================================================
echo   ⛓️ WEB3 ON-CHAIN & GAS FORENSICS (SEPOLIA, MONAD, 0G, CELO)
echo   DuckDB + NetworkX Graph Centrality + Sybil Airdrop Cluster Detection
echo ==============================================================================
echo.

cd /d "%~dp0"

echo [1/3] Verificando dependências Python...
py -3.13 -m pip install -q -r requirements.txt

echo.
echo [2/3] Verificando banco DuckDB e topologia do Grafo NetworkX...
if not exist "data\web3_forensics.duckdb" (
    echo Minerando telemetria e blocos das redes no DuckDB...
    py -3.13 data\pipeline.py
)
if not exist "forensics\graph_metrics.json" (
    echo Construindo grafo direcionado de transações e PageRank...
    py -3.13 forensics\graph_analysis.py
)

echo.
echo [3/3] Iniciando servidor do Dashboard em http://127.0.0.1:8003...
start http://127.0.0.1:8003

echo.
echo Servidor ativo! Pressione Ctrl+C para encerrar.
py -3.13 -m uvicorn app.main:app --host 127.0.0.1 --port 8003
pause
