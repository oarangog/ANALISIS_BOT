import { useState, useEffect } from 'react'
import './App.css'

function App() {
  const [marketData, setMarketData] = useState<any>({})
  const [lastUpdate, setLastUpdate] = useState<string>('')
  const [loading, setLoading] = useState<boolean>(true)

  const fetchAnalysis = async () => {
    try {
      const response = await fetch('http://localhost:8001/analysis')
      const data = await response.json()
      setMarketData(data)
      setLastUpdate(new Date().toLocaleTimeString())
      setLoading(false)
    } catch (error) {
      console.error("Error fetching analysis:", error)
      setLoading(false)
    }
  }

  const handleTrade = async (symbol: string, type: string) => {
    const amountInput = document.getElementById(`amount-${symbol}`) as HTMLInputElement;
    const amount = amountInput ? parseFloat(amountInput.value) : 10;

    // Get current SL/TP from the latest market dat for this asset
    const currentAssetData = marketData.results?.[symbol];
    const sl = currentAssetData ? currentAssetData.sl : 0.0;
    const tp = currentAssetData ? currentAssetData.tp : 0.0;

    try {
      const response = await fetch('http://localhost:8001/trade', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ symbol, type, volume: 0.01, amount, sl, tp })
      });
      const data = await response.json();
      if (data.status === 'ERROR') {
        alert(data.message);
      } else {
        alert(`Operación finalizada: ${data.outcome}.\nNuevo Saldo: $${data.balance}`);
      }
    } catch (err) {
      console.error('Trade error:', err);
      alert("Trade Failed!");
    }
  };

  useEffect(() => {
    fetchAnalysis()
    const interval = setInterval(fetchAnalysis, 10000) // Update every 10s
    return () => clearInterval(interval)
  }, [])

  return (
    <div className="app-container">
      <header className="app-header glass-card">
        <div className="header-left">
          <h1 className="neon-text-cyan">ANALISIS BOT TRADE</h1>
          <p className="subtitle">AI-Driven Trading Intelligence System</p>
        </div>
        <div className="header-right">
          <div className="auto-trading-panel">
            <button
              className={`btn-auto ${marketData.auto_trading?.enabled ? 'active' : ''}`}
              onClick={async () => {
                const enabled = !marketData.auto_trading?.enabled;
                const base = parseFloat((document.getElementById('base-amount') as HTMLInputElement)?.value || '10');
                await fetch('http://localhost:8001/auto-toggle', {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify({ enabled, base_amount: base })
                });
                fetchAnalysis();
              }}
            >
              {marketData.auto_trading?.enabled ? '🛑 DETENER BOT' : '🎮 ENTREGAR MANDO'}
            </button>
            <div className="auto-controls">
              <label>Base $: </label>
              <input
                type="number"
                id="base-amount"
                defaultValue={marketData.auto_trading?.base_amount || 10}
                className="base-input"
              />
            </div>
            {marketData.auto_trading?.enabled && (
              <div className="streak-info">
                Próxima: <span className="neon-text-cyan">${marketData.auto_trading.current_amount.toFixed(2)}</span>
              </div>
            )}
          </div>
          <div className="balance-display">
            <span>Saldo real XM: </span>
            <span className="neon-text-green">{marketData.results?.['EURUSD'] ? `$${marketData.results['EURUSD'].balance.toFixed(2)}` : 'Cargando...'}</span>
          </div>
        </div>
      </header>

      <main>
        <div className="daily-status glass-card">
          <h2>Market Sentiment - {lastUpdate}</h2>
          <div className="sentiment-indicators">
            <span className="badge neon-text-cyan">USD: Strong</span>
            <span className="badge neon-text-magenta">Risk: High</span>
          </div>
        </div>

        {loading ? (
          <p className="neon-text-cyan">Loading live intelligence...</p>
        ) : (
          <div className="grid-dashboard">
            {marketData.results && Object.keys(marketData.results).map((asset) => (
              <div key={asset} className="glass-card asset-card">
                <div className="card-header">
                  <h3 className="neon-text-cyan">{asset} {asset === 'EURUSD' && <span style={{ fontSize: '0.6rem', color: '#666', verticalAlign: 'middle', marginLeft: '5px' }}>(ACTIVO BASE)</span>}</h3>
                  <span className={`status-pill ${marketData.results[asset].status.toLowerCase()}`}>
                    {marketData.results[asset].status}
                  </span>
                </div>
                <div className="divider"></div>
                <p>Operación: <span className={`neon-text-${marketData.results[asset].signal === 'BUY' ? 'cyan' : 'magenta'}`}>{marketData.results[asset].signal || 'WAIT'}</span></p>
                <p>Confianza: <span className="neon-text-magenta">{marketData.results[asset].confidence}%</span></p>
                <p>Inicio: <span className="neon-text-cyan">{marketData.results[asset].entry_time}</span></p>
                <p>Cierre: <span className="neon-text-red">{marketData.results[asset].expiry_time}</span></p>
                <p>Zona: <span className="text-dim">{marketData.results[asset].timezone || 'UTC-5'}</span></p>
                <p>SL: <span className="neon-text-red">{marketData.results[asset].sl}</span></p>
                <p>TP: <span className="neon-text-green">{marketData.results[asset].tp}</span></p>
                {marketData.results[asset].info && <p className="signal-extra">{marketData.results[asset].info}</p>}

                <div className="tradingview-widget glass-card">
                  <p className="neon-text-cyan">Live {asset} Feed (XM Global)</p>
                </div>

                <div className="trade-config">
                  <label>Inversión ($):</label>
                  <input
                    type="number"
                    defaultValue="10"
                    className="amount-input"
                    id={`amount-${asset}`}
                  />
                </div>

                <div className="trade-actions">
                  <button
                    className="trade-button call"
                    onClick={() => handleTrade(asset, 'BUY')}
                  >CALL</button>
                  <button
                    className="trade-button put"
                    onClick={() => handleTrade(asset, 'SELL')}
                  >PUT</button>
                </div>
              </div>
            ))}
          </div>
        )}

        <section className="analysis-tools">
          <div className="glass-card tool-card">
            <h3>Economic News Feed</h3>
            <p className="tool-desc">Real-time impact monitoring (Powered by ERS RF-016)</p>
            <div className="news-item">
              <span className="badge neon-text-magenta">HIGH</span>
              <p>US Inflation Data (PCE) - Caution urged</p>
            </div>
          </div>

          <div className="glass-card tool-card highlight-card">
            <h3>Monitor de Ejecución Real</h3>
            <div className="live-status">
              <span className="label">Último Ticket MT5:</span>
              <span className="value neon-text-green">{marketData.last_ticket || 'Esperando señal...'}</span>
            </div>

            <div className="history-list">
              <h4>Historial de Hoy (Reales):</h4>
              {marketData.history?.map((trade: any) => (
                <div key={trade.ticket} className="history-item">
                  <span>{trade.time}</span>
                  <span>{trade.symbol}</span>
                  <span className={trade.profit >= 0 ? 'neon-text-green' : 'neon-text-red'}>
                    {trade.profit >= 0 ? '+' : ''}${trade.profit.toFixed(2)}
                  </span>
                </div>
              ))}
              {(!marketData.history || marketData.history.length === 0) && <p className="text-dim">Sin operaciones hoy.</p>}
            </div>

            <div className="live-status">
              <span className="label">Estado de Mando:</span>
              <span className={`value ${marketData.auto_trading?.enabled ? 'neon-text-cyan' : 'text-dim'}`}>
                {marketData.auto_trading?.enabled ? '🤖 AUTÓNOMO ACTIVO' : '🛑 MANUAL'}
              </span>
            </div>
          </div>
          <div className="glass-card tool-card">
            <h3>System Settings</h3>
            <div className="lang-switcher">
              <button className="small-button active">ES</button>
              <button className="small-button">EN</button>
              <button className="small-button">PT</button>
            </div>
            <p className="status-connected">Status: Connected as oarangog</p>
            <button className="secondary-button">Advanced Config</button>
          </div>
        </section>
      </main>

      <footer>
        <p>&copy; 2026 ANALISIS BOT TRADE | Premium Trading UI</p>
      </footer>
    </div>
  )
}

export default App
