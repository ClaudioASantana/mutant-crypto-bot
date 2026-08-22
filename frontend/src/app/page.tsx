"use client";
import React, { useState, useEffect, useRef } from "react";
import { createChart, ColorType, CandlestickSeries, HistogramSeries, LineSeries } from "lightweight-charts";

class ErrorBoundary extends React.Component<any, { hasError: boolean, error: any }> {
  constructor(props: any) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: any) {
    return { hasError: true, error };
  }

  componentDidCatch(error: any, errorInfo: any) {
    console.error("ErrorBoundary caught an error", error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return <div style={{ color: "red", padding: "20px" }}><h1>Algo deu errado no React!</h1><pre>{String(this.state.error?.stack || this.state.error)}</pre></div>;
    }
    return this.props.children;
  }
}

export default function Home() {
  const [liveData, setLiveData] = useState<any>({ quote: 0, candle: null });
  const [signal, setSignal] = useState<any>(null);
  const [agentMessage, setAgentMessage] = useState<string>("");
  const [catalog, setCatalog] = useState<any[]>([]);
  const [activeConfig, setActiveConfig] = useState<any>({ timeframe: 300, strategy: "Momentum Breakout" });
  const [autoOptimize, setAutoOptimize] = useState<boolean>(false);
  const [simulatorState, setSimulatorState] = useState<any>(null);
  const [newsStatus, setNewsStatus] = useState<any>(null);
  const [portfolio, setPortfolio] = useState<any>(null);
  const [activeSymbol, setActiveSymbol] = useState<string>("BTC/USDT");
  const [tradePreview, setTradePreview] = useState<any>(null);
  const [aiTaskState, setAiTaskState] = useState<any>({status: "IDLE", reason: "Aguardando gatilho do mercado..."});
  const [cqrsTrades, setCqrsTrades] = useState<any[]>([]);
  const [executingTrade, setExecutingTrade] = useState<boolean>(false);
  
  // Backtest State
  const [currentView, setCurrentView] = useState<"dashboard" | "backtest">("dashboard");
  const [backtestResults, setBacktestResults] = useState<any>(null);
  const [isBacktesting, setIsBacktesting] = useState(false);
  const [backtestStrategy, setBacktestStrategy] = useState("Auto");
  
  // Risk Settings State
  const [riskStake, setRiskStake] = useState<number>(10);
  const [riskStopLoss, setRiskStopLoss] = useState<number>(50);
  const [riskStopGain, setRiskStopGain] = useState<number>(50);
  const [isSavingRisk, setIsSavingRisk] = useState<boolean>(false);
  const [uiError, setUiError] = useState<string>("");

  const [backtestTimeframe, setBacktestTimeframe] = useState(300);
  const [backtestLimit, setBacktestLimit] = useState(1000);
  
  const backtestChartContainerRef = useRef<HTMLDivElement>(null);
  const backtestChartRef = useRef<any>(null);
  const backtestSeriesRef = useRef<any>(null);
  
  const activeSymbolRef = useRef(activeSymbol);
  const httpUrl = typeof window === "undefined"
    ? ""
    : (process.env.NEXT_PUBLIC_BACKEND_HTTP_URL || `http://${window.location.hostname}:${process.env.NEXT_PUBLIC_API_PORT || 8000}`);
  const backendWsBaseUrl = typeof window === "undefined"
    ? ""
    : (process.env.NEXT_PUBLIC_BACKEND_WS_URL || `ws://${window.location.hostname}:${process.env.NEXT_PUBLIC_API_PORT || 8000}/ws`);
  const apiAuthToken = process.env.NEXT_PUBLIC_API_AUTH_TOKEN?.trim() || "";
  const wsUrl = backendWsBaseUrl && apiAuthToken
    ? `${backendWsBaseUrl}${backendWsBaseUrl.includes("?") ? "&" : "?"}token=${encodeURIComponent(apiAuthToken)}`
    : backendWsBaseUrl;
  const authHeaders = apiAuthToken ? { "X-API-Key": apiAuthToken } : {};

  const ensureOk = async (res: Response, context: string) => {
    if (res.ok) {
      return res;
    }

    let detail = `${res.status} ${res.statusText}`;
    try {
      const payload = await res.json();
      if (payload?.detail) {
        detail = typeof payload.detail === "string" ? payload.detail : JSON.stringify(payload.detail);
      }
    } catch {
      // mantém fallback textual quando a resposta não for JSON
    }

    throw new Error(`${context}: ${detail}`);
  };

  const reportUiError = (message: string, error?: unknown) => {
    console.error(message, error);
    setUiError(message);
  };

  useEffect(() => {
    if (!apiAuthToken) {
      setUiError("NEXT_PUBLIC_API_AUTH_TOKEN não configurado. As ações protegidas da UI ficarão bloqueadas.");
    }
  }, [apiAuthToken]);

  useEffect(() => {
    setAiTaskState({
      status: "IDLE",
      reason: "Sem telemetria real do pipeline de IA no backend. Painel informativo apenas."
    });
  }, []);

  useEffect(() => {
    activeSymbolRef.current = activeSymbol;
  }, [activeSymbol]);

  const ws = useRef<WebSocket | null>(null);
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartSeriesRef = useRef<any>(null);
  const priceLinesRef = useRef<any[]>([]);

  useEffect(() => {
    // Connect to WebSocket
    ws.current = new WebSocket(wsUrl);

    ws.current.onopen = () => {
      console.log("Connected to backend WS");
      setUiError("");
      ws.current?.send(JSON.stringify({ command: "WATCH_SYMBOL", symbol: activeSymbolRef.current }));
    };
    
    ws.current.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      if (msg?.event === "error") {
        reportUiError(typeof msg.data === "string" ? msg.data : "Erro recebido do WebSocket.");
        return;
      }
      
      // Filtra mensagens que não são do ativo selecionado (se a mensagem tiver symbol)
      if (msg.symbol && msg.symbol !== activeSymbolRef.current) {
        return;
      }
      
      if (msg.event === "tick") {
        setLiveData(msg.data);
      } else if (msg.event === "signal") {
        setSignal(msg.data);
      } else if (msg.event === "agent_message") {
        setAgentMessage(msg.data);
      } else if (msg.event === "catalog") {
        setCatalog(msg.data.catalog);
        setActiveConfig(msg.data.active_config);
        setAutoOptimize(msg.data.auto_optimize);
        if (msg.data.simulator) setSimulatorState(msg.data.simulator);
        if (msg.data.news_status) setNewsStatus(msg.data.news_status);
      } else if (msg.event === "simulator") {
        setSimulatorState(msg.data.simulator || msg.data);
        if (msg.data.news_status) setNewsStatus(msg.data.news_status);
      } else if (msg.event === "trade_preview") {
        setTradePreview(msg.data);
      } else if (msg.event === "active_symbol") {
        setActiveSymbol(msg.data);
      } else if (msg.event === "chart_history") {
        if (chartSeriesRef.current && typeof chartSeriesRef.current.setData === 'function') {
          chartSeriesRef.current.setData(msg.data);
        } else {
          console.warn("Chart series ref não inicializado ou setData indisponível, ignorando update.");
        }
      }
    };

    ws.current.onerror = (event) => {
      reportUiError("Falha na conexão WebSocket com o backend. Verifique token e disponibilidade do servidor.", event);
    };

    ws.current.onclose = (event) => {
      if (event.code === 4403) {
        reportUiError("WebSocket rejeitado por autenticação. Verifique NEXT_PUBLIC_API_AUTH_TOKEN.");
      }
    };

    return () => {
      if (ws.current) ws.current.close();
    };
  }, [wsUrl]);

  useEffect(() => {
    const fetchPortfolio = async () => {
      try {
        const res = await fetch(`${httpUrl}/portfolio`);
        await ensureOk(res, "Falha ao carregar portfólio");
        const data = await res.json();
        setPortfolio(data);
      } catch (e) {
        reportUiError("Falha ao carregar portfólio do backend.", e);
      }
    };
    fetchPortfolio();
    const interval = setInterval(fetchPortfolio, 5000);

    const fetchRisk = async () => {
      try {
        const res = await fetch(`${httpUrl}/api/risk_settings`);
        await ensureOk(res, "Falha ao carregar parâmetros de risco");
        const data = await res.json();
        setRiskStake(data.stake_initial);
        setRiskStopLoss(data.daily_stop_loss);
        setRiskStopGain(data.daily_stop_gain);
      } catch (e) {
        reportUiError("Falha ao carregar parâmetros de risco.", e);
      }
    };
    fetchRisk();

    const fetchCqrsTrades = async () => {
      try {
        const res = await fetch(`${httpUrl}/api/cqrs/active_trades?identity=default`);
        await ensureOk(res, "Falha ao carregar posições CQRS");
        const data = await res.json();
        if (data.status === "success") {
          setCqrsTrades(data.trades);
        }
      } catch (e) {
        reportUiError("Falha ao carregar posições CQRS.", e);
      }
    };
    fetchCqrsTrades();
    const cqrsInterval = setInterval(fetchCqrsTrades, 3000);

    return () => {
      clearInterval(interval);
      clearInterval(cqrsInterval);
    };
  }, [httpUrl]);

  useEffect(() => {
    if (currentView !== 'dashboard' || !chartContainerRef.current) return;
    
    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: '#d1d4dc',
      },
      grid: {
        vertLines: { color: 'rgba(42, 46, 57, 0)' },
        horzLines: { color: 'rgba(42, 46, 57, 0.2)' },
      },
      width: chartContainerRef.current.clientWidth,
      height: 250,
      timeScale: {
        timeVisible: true,
        secondsVisible: false,
      }
    });

    const candlestickSeries = chart.addSeries(CandlestickSeries, {
        upColor: '#26a69a',
        downColor: '#ef5350',
        borderVisible: false,
        wickUpColor: '#26a69a',
        wickDownColor: '#ef5350',
    });
    chartSeriesRef.current = candlestickSeries;

    const handleResize = () => {
      if (chartContainerRef.current) {
        chart.applyOptions({ width: chartContainerRef.current.clientWidth });
      }
    };
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      chart.remove();
      chartSeriesRef.current = null;
      priceLinesRef.current = [];
    };
  }, [currentView]);


  useEffect(() => {
    if (chartSeriesRef.current && typeof chartSeriesRef.current.setData === 'function') {
      // Limpa o gráfico imediatamente para evitar bug de escala ao trocar de ativo
      chartSeriesRef.current.setData([]);
    }

    const fetchHistory = async () => {
      try {
        const res = await fetch(`${httpUrl}/api/chart_history?symbol=${activeSymbol}&limit=200`);
        await ensureOk(res, "Falha ao carregar histórico do gráfico");
        const result = await res.json();
        if (chartSeriesRef.current && typeof chartSeriesRef.current.setData === 'function' && result.data) {
          chartSeriesRef.current.setData(result.data);
        }
      } catch (e) {
        reportUiError("Falha ao carregar histórico do gráfico.", e);
      }
    };

    if (activeSymbol) {
      fetchHistory();
    }
  }, [activeSymbol]);

  useEffect(() => {
    if (chartSeriesRef.current && currentView === 'dashboard' && liveData.candle) {
        const data = {
            time: liveData.candle.epoch,
            open: liveData.candle.open,
            high: liveData.candle.high,
            low: liveData.candle.low,
            close: liveData.candle.close,
        };
        try {
            chartSeriesRef.current.update(data);
        } catch (e) {
            console.warn("Ignoring tick update error (possibly older timestamp)", e);
        }
    }
  }, [liveData.candle]);

  useEffect(() => {
    if (!chartSeriesRef.current || currentView !== 'dashboard') return;
    
    // Clear previous lines
    priceLinesRef.current.forEach(line => chartSeriesRef.current.removePriceLine(line));
    priceLinesRef.current = [];

    if (tradePreview) {
      const callTpLine = chartSeriesRef.current.createPriceLine({
        price: tradePreview.call_tp,
        color: '#10b981',
        lineWidth: 1,
        lineStyle: 3, // Dotted
        axisLabelVisible: true,
        title: 'C. TP',
      });
      const callSlLine = chartSeriesRef.current.createPriceLine({
        price: tradePreview.call_sl,
        color: '#ef4444',
        lineWidth: 1,
        lineStyle: 3,
        axisLabelVisible: true,
        title: 'C. SL',
      });
      const putTpLine = chartSeriesRef.current.createPriceLine({
        price: tradePreview.put_tp,
        color: '#10b981',
        lineWidth: 1,
        lineStyle: 3,
        axisLabelVisible: true,
        title: 'P. TP',
      });
      const putSlLine = chartSeriesRef.current.createPriceLine({
        price: tradePreview.put_sl,
        color: '#ef4444',
        lineWidth: 1,
        lineStyle: 3,
        axisLabelVisible: true,
        title: 'P. SL',
      });
      
      priceLinesRef.current = [callTpLine, callSlLine, putTpLine, putSlLine];
    }
  }, [tradePreview]);

  // Modo Autônomo: Os métodos handleApprove e handleIgnore foram removidos.
  // O backend agora executa ordens e salva logs automaticamente.

  const handleSetConfig = (timeframe: number, strategy: string) => {
    if (ws.current) {
      ws.current.send(JSON.stringify({ command: "SET_CONFIG", timeframe, strategy }));
      setActiveConfig({ ...activeConfig, timeframe, strategy });
    }
  };

  const handleApplyStrategy = (strategyConfig: any) => {
    if (ws.current) {
      ws.current.send(JSON.stringify({
        command: "SET_CONFIG",
        timeframe: strategyConfig.timeframe,
        strategy: strategyConfig.strategy,
        rsi_oversold: strategyConfig.rsi_oversold,
        rsi_overbought: strategyConfig.rsi_overbought
      }));
      setActiveConfig({
        timeframe: strategyConfig.timeframe,
        strategy: strategyConfig.strategy,
        rsi_oversold: strategyConfig.rsi_oversold,
        rsi_overbought: strategyConfig.rsi_overbought
      });
      setCurrentView("dashboard");
    }
  };

  const handleToggleAutoOptimize = () => {
    if (ws.current) {
      ws.current.send(JSON.stringify({ command: "TOGGLE_AUTO_OPTIMIZE" }));
    }
  };

  const handleToggleGlobalMutant = () => {
    if (ws.current) {
      ws.current.send(JSON.stringify({ command: "TOGGLE_AUTO_OPTIMIZE_ALL", active: !autoOptimize }));
    }
  };

  const runAdvancedBacktest = async () => {
    setIsBacktesting(true);
    setBacktestResults(null);
    try {
      const res = await fetch(`${httpUrl}/api/backtest_advanced`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          symbol: activeSymbol,
          timeframe: backtestTimeframe,
          limit: backtestLimit,
          strategy: backtestStrategy
        })
      });
      await ensureOk(res, "Falha ao executar backtest");
      const data = await res.json();
      setBacktestResults(data);
      setUiError("");
    } catch (err) {
      reportUiError("Falha ao executar backtest avançado.", err);
    }
    setIsBacktesting(false);
  };

  const saveRiskSettings = async () => {
    if (!apiAuthToken) {
      reportUiError("Token ausente na UI. Configure NEXT_PUBLIC_API_AUTH_TOKEN para salvar risco.");
      return;
    }

    setIsSavingRisk(true);
    try {
      const res = await fetch(`${httpUrl}/api/risk_settings`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders },
        body: JSON.stringify({
          stake_initial: riskStake,
          daily_stop_loss: riskStopLoss,
          daily_stop_gain: riskStopGain
        })
      });
      await ensureOk(res, "Falha ao salvar parâmetros de risco");
      setUiError("");
    } catch (e) {
      reportUiError("Erro ao salvar configurações de risco.", e);
    }
    setIsSavingRisk(false);
  };

  const handleManualTrade = async (direction: string) => {
    if (!apiAuthToken) {
      reportUiError("Token ausente na UI. Configure NEXT_PUBLIC_API_AUTH_TOKEN para executar trade manual.");
      return;
    }

    const atr = Number(tradePreview?.atr);
    if (!Number.isFinite(atr) || atr <= 0) {
      reportUiError("Trade manual bloqueado: ATR real indisponível para o ativo atual.");
      return;
    }

    if (!Number.isFinite(Number(liveData.quote)) || Number(liveData.quote) <= 0) {
      reportUiError("Trade manual bloqueado: preço atual indisponível.");
      return;
    }

    setExecutingTrade(true);
    try {
      const res = await fetch(`${httpUrl}/api/cqrs/execute_trade?identity=default`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders },
        body: JSON.stringify({
          symbol: activeSymbol,
          direction: direction,
          timeframe: activeConfig?.timeframe || 300,
          strategy: "Manual UI",
          entry_price: liveData.quote,
          atr
        })
      });
      await ensureOk(res, "Falha ao executar trade manual");
      setUiError("");
    } catch (e) {
      reportUiError("Erro ao executar trade manual.", e);
    }
    setExecutingTrade(false);
  };


  // Efeito para desenhar linhas de TP/SL no gráfico
  useEffect(() => {
    if (currentView !== 'backtest' || !backtestChartContainerRef.current) return;
    
    const chart = createChart(backtestChartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: '#d1d4dc',
      },
      grid: {
        vertLines: { color: 'rgba(42, 46, 57, 0)' },
        horzLines: { color: 'rgba(42, 46, 57, 0.2)' },
      },
      width: backtestChartContainerRef.current.clientWidth,
      height: 400,
      timeScale: {
        timeVisible: true,
        secondsVisible: false,
      }
    });

    const candlestickSeries = chart.addSeries(CandlestickSeries, {
        upColor: '#26a69a',
        downColor: '#ef5350',
        borderVisible: false,
        wickUpColor: '#26a69a',
        wickDownColor: '#ef5350',
    });
    
    const volumeSeries = chart.addSeries(HistogramSeries, {
      color: '#26a69a',
      priceFormat: { type: 'volume' },
      priceScaleId: '', // overlay
    });
    
    chart.priceScale('').applyOptions({
      scaleMargins: {
        top: 0.8,
        bottom: 0,
      },
    });

    const bbUpperSeries = chart.addSeries(LineSeries, { color: 'rgba(33, 150, 243, 0.4)', lineWidth: 1 });
    const bbMiddleSeries = chart.addSeries(LineSeries, { color: 'rgba(255, 152, 0, 0.4)', lineWidth: 1 });
    const bbLowerSeries = chart.addSeries(LineSeries, { color: 'rgba(33, 150, 243, 0.4)', lineWidth: 1 });
    
    const macdLineSeries = chart.addSeries(LineSeries, { color: '#2962FF', lineWidth: 1, priceScaleId: 'macd' });
    const macdSignalSeries = chart.addSeries(LineSeries, { color: '#FF6D00', lineWidth: 1, priceScaleId: 'macd' });
    const macdHistSeries = chart.addSeries(HistogramSeries, { priceScaleId: 'macd' });
    
    chart.priceScale('macd').applyOptions({
      scaleMargins: {
        top: 0.8,
        bottom: 0,
      },
    });
    
    backtestChartRef.current = chart;
    backtestSeriesRef.current = candlestickSeries;

    const handleResize = () => {
      if (backtestChartContainerRef.current) {
        chart.applyOptions({ width: backtestChartContainerRef.current.clientWidth });
      }
    };
    window.addEventListener('resize', handleResize);
    
    if (backtestResults?.history) {
      try {
        candlestickSeries.setData(backtestResults.history);
        
        const volumeData: any[] = [];
        const bbUpperData: any[] = [];
        const bbMiddleData: any[] = [];
        const bbLowerData: any[] = [];
        const macdLineData: any[] = [];
        const macdSignalData: any[] = [];
        const macdHistData: any[] = [];
        
        backtestResults.history.forEach((item: any) => {
          if (item.volume !== undefined) {
            volumeData.push({ time: item.time, value: item.volume, color: item.close >= item.open ? 'rgba(38, 166, 154, 0.5)' : 'rgba(239, 83, 80, 0.5)' });
          }
          if (item.bb_upper !== undefined) bbUpperData.push({ time: item.time, value: item.bb_upper });
          if (item.bb_middle !== undefined) bbMiddleData.push({ time: item.time, value: item.bb_middle });
          if (item.bb_lower !== undefined) bbLowerData.push({ time: item.time, value: item.bb_lower });
          
          if (item.macd_line !== undefined) macdLineData.push({ time: item.time, value: item.macd_line });
          if (item.macd_signal !== undefined) macdSignalData.push({ time: item.time, value: item.macd_signal });
          if (item.macd_hist !== undefined) macdHistData.push({ time: item.time, value: item.macd_hist, color: item.macd_hist >= 0 ? '#26a69a' : '#ef5350' });
        });
        
        if (volumeData.length > 0) volumeSeries.setData(volumeData);
        if (bbUpperData.length > 0) bbUpperSeries.setData(bbUpperData);
        if (bbMiddleData.length > 0) bbMiddleSeries.setData(bbMiddleData);
        if (bbLowerData.length > 0) bbLowerSeries.setData(bbLowerData);
        if (macdLineData.length > 0) macdLineSeries.setData(macdLineData);
        if (macdSignalData.length > 0) macdSignalSeries.setData(macdSignalData);
        if (macdHistData.length > 0) macdHistSeries.setData(macdHistData);
        if (backtestResults.trades) {
          const markers = backtestResults.trades.map((t: any) => ({
            time: t.entry_time,
            position: t.signal === 'CALL' ? 'belowBar' : 'aboveBar',
            color: t.signal === 'CALL' ? '#26a69a' : '#ef5350',
            shape: t.signal === 'CALL' ? 'arrowUp' : 'arrowDown',
            text: `${t.signal} (${t.profit > 0 ? '+' : ''}${t.profit.toFixed(2)})`
          }));
          
          // Lightweight-charts exige que os marcadores estejam ordenados por tempo e sem tempos duplicados exatos
          const uniqueMarkers: any[] = [];
          const seenTimes = new Set();
          markers.sort((a: any, b: any) => a.time - b.time).forEach((m: any) => {
            if (!seenTimes.has(m.time)) {
              seenTimes.add(m.time);
              uniqueMarkers.push(m);
            }
          });
          
          if (uniqueMarkers.length > 0) {
            (candlestickSeries as any).setMarkers(uniqueMarkers);
          }
        }
      } catch (err) {
        console.error("Erro ao definir dados/marcadores do backtest no gráfico:", err);
      }
    }

    return () => {
      window.removeEventListener('resize', handleResize);
      chart.remove();
      backtestChartRef.current = null;
      backtestSeriesRef.current = null;
    };
  }, [currentView, backtestResults]);

  const handleChangeSymbol = (symbol: string) => {
    if (ws.current) {
      ws.current.send(JSON.stringify({ command: "WATCH_SYMBOL", symbol }));
      setActiveSymbol(symbol);
      // Limpar dados do ativo anterior para evitar exibição de dados defasados
      setTradePreview(null);
      setCatalog([]);
      setSignal(null);
      setAgentMessage("");
    }
  };

  return (
    <ErrorBoundary>
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden' }}>
      {/* Top Navbar */}
      <div style={{ padding: '16px 20px', background: 'rgba(0,0,0,0.4)', borderBottom: '1px solid rgba(255,255,255,0.1)', display: 'flex', gap: '16px', alignItems: 'center' }}>
         <div style={{ fontSize: '1.2rem', fontWeight: 'bold', marginRight: '20px' }}>MutantCrypto</div>
         <button 
           onClick={() => setCurrentView('dashboard')}
           style={{ background: currentView === 'dashboard' ? 'var(--accent)' : 'transparent', color: currentView === 'dashboard' ? '#000' : '#fff', border: 'none', padding: '8px 16px', borderRadius: '4px', fontWeight: 'bold', cursor: 'pointer' }}
         >
           Dashboard Live
         </button>
         <button 
           onClick={() => setCurrentView('backtest')}
           style={{ background: currentView === 'backtest' ? 'var(--accent)' : 'transparent', color: currentView === 'backtest' ? '#000' : '#fff', border: 'none', padding: '8px 16px', borderRadius: '4px', fontWeight: 'bold', cursor: 'pointer' }}
         >
           Laboratório (Backtest)
         </button>
      </div>
      
      {currentView === 'dashboard' ? (
        <div className="layout-container" style={{ flex: 1, overflow: 'auto' }}>
          {/* Esquerda: Agente RAG e Controles */}
          <div style={{ display: "flex", flexDirection: "column", gap: "20px", minWidth: 0 }}>
            
            <header>
              <h1>Cockpit de Decisão</h1>
              <p style={{ opacity: 0.6 }}>Análise Quantitativa + IA</p>
              {uiError && (
                <div style={{
                  marginTop: "12px",
                  padding: "10px 12px",
                  borderRadius: "8px",
                  background: "rgba(239,68,68,0.15)",
                  border: "1px solid rgba(239,68,68,0.35)",
                  color: "#fecaca",
                  fontSize: "0.85rem"
                }}>
                  {uiError}
                </div>
              )}
            </header>

        {/* Seletor de Ativo */}
        <div className="glass" style={{ padding: "16px", display: "flex", flexDirection: "column", gap: "10px" }}>
          <h3 style={{ margin: 0, fontSize: "1rem", color: "var(--accent)" }}>Ativo Operacional</h3>
          <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
            {/* ATIVOS CRIPTO */}
            {["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT"].map(sym => {
              const isSelected = activeSymbol === sym;
              return (
                <button
                  key={sym}
                  onClick={() => handleChangeSymbol(sym)}
                  style={{
                    flex: "1 1 20%",
                    padding: "6px 8px",
                    background: isSelected ? "var(--accent)" : "rgba(255,255,255,0.05)",
                    color: isSelected ? "#000" : "#fff",
                    border: `1px solid ${isSelected ? "var(--accent)" : "rgba(255,255,255,0.1)"}`,
                    borderRadius: "6px",
                    cursor: "pointer",
                    fontSize: "0.85rem",
                    fontWeight: isSelected ? "bold" : "normal",
                    transition: "all 0.2s"
                  }}
                >
                  {sym}
                </button>
              );
            })}
          </div>
        </div>

        {/* Gerenciamento de Risco Global */}
        <div className="glass" style={{ padding: "16px", display: "flex", flexDirection: "column", gap: "12px" }}>
          <h3 style={{ margin: 0, fontSize: "1rem", color: "var(--accent)" }}>🛡️ Gerenciamento de Risco (Global)</h3>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
            <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
              <label style={{ fontSize: "0.85rem", opacity: 0.8 }}>Stake Inicial ($)</label>
              <input type="number" value={riskStake} onChange={e => setRiskStake(Number(e.target.value))} style={{ padding: "8px", background: "rgba(0,0,0,0.4)", color: "white", border: "1px solid rgba(255,255,255,0.1)", borderRadius: "4px" }} />
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
              <label style={{ fontSize: "0.85rem", opacity: 0.8 }}>Stop Loss ($)</label>
              <input type="number" value={riskStopLoss} onChange={e => setRiskStopLoss(Number(e.target.value))} style={{ padding: "8px", background: "rgba(0,0,0,0.4)", color: "white", border: "1px solid rgba(255,255,255,0.1)", borderRadius: "4px" }} />
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
              <label style={{ fontSize: "0.85rem", opacity: 0.8 }}>Stop Gain ($)</label>
              <input type="number" value={riskStopGain} onChange={e => setRiskStopGain(Number(e.target.value))} style={{ padding: "8px", background: "rgba(0,0,0,0.4)", color: "white", border: "1px solid rgba(255,255,255,0.1)", borderRadius: "4px" }} />
            </div>
          </div>
          <button 
            onClick={saveRiskSettings} 
            disabled={isSavingRisk}
            style={{ 
              marginTop: "8px", padding: "10px", background: "var(--accent)", color: "#000", border: "none", borderRadius: "6px", fontWeight: "bold", cursor: isSavingRisk ? "not-allowed" : "pointer", opacity: isSavingRisk ? 0.7 : 1
            }}
          >
            {isSavingRisk ? "⏳ Salvando..." : "💾 Salvar Limites"}
          </button>
        </div>

        <div className="glass" style={{ flex: 1, padding: "20px", display: "flex", flexDirection: "column" }}>
          <h3 style={{ marginBottom: "16px", color: "var(--accent)" }}>🧠 Análise da IA</h3>
          <div style={{ 
            flex: 1, 
            background: "rgba(0,0,0,0.3)", 
            borderRadius: "8px", 
            padding: "16px", 
            overflowY: "auto",
            fontFamily: "var(--font-geist-mono), monospace",
            fontSize: "0.95rem",
            lineHeight: "1.6",
            whiteSpace: "pre-wrap"
          }}>
            {agentMessage ? (
              <p>{agentMessage}</p>
            ) : (
              <p style={{ opacity: 0.4 }}>Aguardando formação de sinais no mercado...</p>
            )}
          </div>
        </div>

        <div className="glass" style={{ padding: "20px", overflowX: "auto" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
            <h3 style={{ margin: 0 }}>📊 Catalogador de Sinais</h3>
            <div style={{ display: 'flex', gap: '8px' }}>
              <button 
                onClick={handleToggleAutoOptimize}
                style={{ 
                  padding: "8px 16px", 
                  borderRadius: "20px", 
                  border: "none",
                  background: autoOptimize ? "#10b981" : "rgba(255,255,255,0.1)",
                  color: "white",
                  fontWeight: "bold",
                  cursor: "pointer",
                  transition: "0.2s",
                  display: "flex",
                  alignItems: "center",
                  gap: "8px"
                }}
              >
                {autoOptimize ? "🧬 Mutante Ativo" : "🔧 Modo Manual"}
              </button>
              <button 
                onClick={handleToggleGlobalMutant}
                style={{ 
                  padding: "8px 16px", 
                  borderRadius: "20px", 
                  border: `1px solid ${autoOptimize ? "#10b981" : "rgba(255,255,255,0.2)"}`,
                  background: "transparent",
                  color: autoOptimize ? "#10b981" : "white",
                  fontWeight: "bold",
                  cursor: "pointer",
                  transition: "0.2s",
                  display: "flex",
                  alignItems: "center",
                  gap: "8px"
                }}
              >
                🧬 Mutante Global
              </button>
            </div>
          </div>
          <p style={{ fontSize: "0.85rem", opacity: 0.7, marginBottom: "16px" }}>
            {autoOptimize ? 
              "O robô está varrendo a tabela e se reconfigurando sozinho a cada vela fechada!"
              : "Clique no card para alterar a estratégia base do robô autônomo."
            }
          </p>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: "8px", minWidth: "500px" }}>
            <div style={{ fontWeight: "bold", opacity: 0.5 }}>Timeframe</div>
            <div style={{ fontWeight: "bold", opacity: 0.5, textAlign: "center" }}>EMA+MACD</div>
            <div style={{ fontWeight: "bold", opacity: 0.5, textAlign: "center" }}>Bollinger</div>
            <div style={{ fontWeight: "bold", opacity: 0.5, textAlign: "center" }}>VWAP</div>
            <div style={{ fontWeight: "bold", opacity: 0.5, textAlign: "center" }}>SMC</div>
            
            {[60, 300, 900].map(tf => (
              <React.Fragment key={tf}>
                <div style={{ display: "flex", alignItems: "center", fontWeight: "bold" }}>
                  M{tf / 60}
                </div>
                {["Momentum Breakout"].map(s => {
                  const cat = (catalog || []).find(x => x.timeframe === tf && x.strategy === s);
                  const winRate = cat?.stats?.win_rate ?? 0;
                  const pnl = cat?.stats?.pnl_usdt ?? 0;
                  const isManualActive = activeConfig?.timeframe === tf && activeConfig?.strategy === s;
                  const isActive = autoOptimize ? (pnl > 0) : isManualActive;
                  return (
                    <div 
                      key={`${tf}-${s}`} 
                      onClick={() => !autoOptimize && handleSetConfig(tf, s)}
                      style={{ 
                        padding: "8px", 
                        borderRadius: "4px", 
                        textAlign: "center",
                        cursor: autoOptimize ? "not-allowed" : "pointer",
                        opacity: autoOptimize && !isActive ? 0.4 : 1,
                        background: pnl > 0 ? "rgba(38, 166, 154, 0.2)" : (pnl < 0 ? "rgba(239, 83, 80, 0.2)" : "rgba(255, 255, 255, 0.1)"),
                        border: isActive ? "2px solid var(--accent)" : "2px solid transparent",
                        transition: "all 0.2s"
                      }}
                    >
                      <div style={{ fontWeight: "bold", color: pnl > 0 ? "var(--success)" : (pnl < 0 ? "var(--danger)" : "white") }}>
                        {cat ? `${pnl > 0 ? '+' : ''}$${pnl.toFixed(2)}` : "--"}
                      </div>
                      <div style={{ fontSize: "0.75rem", opacity: 0.6 }}>
                        {cat ? `Win Rate: ${winRate}%` : "--"}
                      </div>
                    </div>
                  );
                })}
              </React.Fragment>
            ))}
          </div>
        </div>
        
        {/* Status de Notícias (Calendário Econômico) */}
        {newsStatus && (
          <div style={{ marginBottom: "20px", padding: "12px 20px", background: newsStatus.safe ? "rgba(38, 166, 154, 0.15)" : "rgba(239, 83, 80, 0.2)", borderRadius: "8px", border: `1px solid ${newsStatus.safe ? "var(--success)" : "var(--danger)"}`, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
              <span style={{ fontSize: "1.5rem" }}>{newsStatus.safe ? "🟢" : "🔴"}</span>
              <div>
                <h4 style={{ margin: 0, color: newsStatus.safe ? "var(--success)" : "var(--danger)" }}>
                  {newsStatus.safe ? "Mercado Seguro para Operar" : "ZONA DE NOTÍCIA (Pausa Ativa)"}
                </h4>
                <p style={{ margin: 0, fontSize: "0.85rem", opacity: 0.8 }}>
                  {newsStatus.reason}
                </p>
              </div>
            </div>
            {newsStatus.next_event && (
              <div style={{ textAlign: "right" }}>
                <div style={{ fontSize: "0.7rem", opacity: 0.6, textTransform: "uppercase" }}>Próxima Notícia (3 Touros)</div>
                <div style={{ fontWeight: "bold" }}>{newsStatus.next_event.name}</div>
                <div style={{ fontSize: "0.85rem", opacity: 0.8 }}>Impacto: {newsStatus.next_event.impact}</div>
              </div>
            )}
          </div>
        )}

        {/* Pre-Trade Preview Card */}
        <div className="glass" style={{ padding: "20px", marginBottom: "0" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "14px" }}>
            <h3 style={{ margin: 0, color: "var(--accent)" }}>🎯 Próxima Entrada Estimada</h3>
            {tradePreview && (
              <span style={{ fontSize: "0.75rem", opacity: 0.6, background: "rgba(255,255,255,0.05)", padding: "4px 10px", borderRadius: "20px" }}>
                {tradePreview.strategy} • {tradePreview.timeframe} • ATR: {tradePreview.atr}
              </span>
            )}
          </div>
          {!tradePreview ? (
            <div style={{ opacity: 0.5, fontSize: "0.85rem", textAlign: "center", padding: "12px 0" }}>Aguardando fechamento da próxima vela...</div>
          ) : (
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
              {/* CALL side */}
              <div className="animate-pulse-success" style={{ background: "rgba(16,185,129,0.08)", border: "1px solid rgba(16,185,129,0.25)", borderRadius: "10px", padding: "14px" }}>
                <div style={{ color: "var(--success)", fontWeight: 700, fontSize: "0.8rem", marginBottom: "10px", letterSpacing: "0.05em" }}>▲ CALL (COMPRA)</div>
                <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.82rem" }}>
                    <span style={{ opacity: 0.65 }}>Entrada</span>
                    <span key={`call-entry-${tradePreview.current_price}`} className="animate-flash" style={{ fontWeight: 600 }}>${tradePreview.current_price.toLocaleString()}</span>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.82rem" }}>
                    <span style={{ opacity: 0.65 }}>Take Profit</span>
                    <span key={`call-tp-${tradePreview.call_tp}`} className="animate-flash" style={{ color: "var(--success)", fontWeight: 600 }}>${tradePreview.call_tp.toLocaleString()}</span>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.82rem" }}>
                    <span style={{ opacity: 0.65 }}>Stop Loss</span>
                    <span key={`call-sl-${tradePreview.call_sl}`} className="animate-flash" style={{ color: "var(--danger)", fontWeight: 600 }}>${tradePreview.call_sl.toLocaleString()}</span>
                  </div>
                </div>
              </div>
              {/* PUT side */}
              <div className="animate-pulse-danger" style={{ background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.25)", borderRadius: "10px", padding: "14px" }}>
                <div style={{ color: "var(--danger)", fontWeight: 700, fontSize: "0.8rem", marginBottom: "10px", letterSpacing: "0.05em" }}>▼ PUT (VENDA)</div>
                <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.82rem" }}>
                    <span style={{ opacity: 0.65 }}>Entrada</span>
                    <span key={`put-entry-${tradePreview.current_price}`} className="animate-flash" style={{ fontWeight: 600 }}>${tradePreview.current_price.toLocaleString()}</span>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.82rem" }}>
                    <span style={{ opacity: 0.65 }}>Take Profit</span>
                    <span key={`put-tp-${tradePreview.put_tp}`} className="animate-flash" style={{ color: "var(--success)", fontWeight: 600 }}>${tradePreview.put_tp.toLocaleString()}</span>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.82rem" }}>
                    <span style={{ opacity: 0.65 }}>Stop Loss</span>
                    <span key={`put-sl-${tradePreview.put_sl}`} className="animate-flash" style={{ color: "var(--danger)", fontWeight: 600 }}>${tradePreview.put_sl.toLocaleString()}</span>
                  </div>
                </div>
              </div>
              {/* Bottom bar: margin & exposure */}
              <div style={{ gridColumn: "1 / -1", background: "rgba(255,255,255,0.04)", borderRadius: "8px", padding: "10px 14px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div style={{ fontSize: "0.8rem" }}>
                  <span style={{ opacity: 0.6 }}>Margem: </span>
                  <span style={{ fontWeight: 600, color: "var(--accent)" }}>${tradePreview.margin}</span>
                  <span style={{ opacity: 0.4, margin: "0 8px" }}>×</span>
                  <span style={{ opacity: 0.6 }}>{tradePreview.leverage}x = </span>
                  <span style={{ fontWeight: 600 }}>${tradePreview.exposure} exposição</span>
                </div>
                <div style={{ fontSize: "0.75rem", opacity: 0.5 }}>{tradePreview.rr_ratio}</div>
              </div>
            </div>
          )}
        </div>

        {/* Módulo Simulador Financeiro (Movido para dentro da coluna esquerda) */}
        {simulatorState && (
        <div style={{ display: "flex", gap: "20px" }}>
          <div className="glass" style={{ padding: "20px", flex: 1 }}>
            <h3 style={{ marginBottom: "16px", color: "var(--accent)" }}>💳 Conta Futuros (USDT)</h3>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", marginBottom: "8px" }}>
              <span style={{ fontSize: "0.9rem", opacity: 0.7 }}>Saldo USDT</span>
              <span style={{ fontSize: "1.5rem", fontWeight: "bold" }}>${simulatorState.balance.toFixed(2)}</span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "12px", background: "rgba(0,0,0,0.2)", borderRadius: "8px" }}>
              <span style={{ fontSize: "0.85rem" }}>Lucro/Prejuízo (PnL)</span>
              <span style={{ fontWeight: "bold", color: simulatorState.pnl >= 0 ? "var(--success)" : "var(--danger)" }}>
                {simulatorState.pnl >= 0 ? "+" : ""}${simulatorState.pnl.toFixed(2)}
              </span>
            </div>
            {simulatorState.risk && (
              <div style={{ marginTop: "16px", padding: "12px", background: "rgba(0,0,0,0.3)", borderRadius: "8px", fontSize: "0.85rem" }}>
                <div style={{ marginBottom: "8px", fontWeight: "bold", color: "var(--accent)" }}>🛡️ Gestão de Risco (Crypto)</div>
                
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "6px" }}>
                  <span style={{ opacity: 0.7 }}>Alavancagem</span>
                  <span>{simulatorState.risk.leverage}x</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "6px" }}>
                  <span style={{ opacity: 0.7 }}>Margem por Trade</span>
                  <span style={{ fontWeight: "bold" }}>${simulatorState.risk.next_margin.toFixed(2)}</span>
                </div>
                
                {/* Stop Gain Progress */}
                <div style={{ marginTop: "12px" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.7rem", opacity: 0.8, marginBottom: "4px" }}>
                    <span>Stop Gain (${simulatorState.risk.stop_gain})</span>
                    <span>{Math.min(100, Math.max(0, (simulatorState.pnl / simulatorState.risk.stop_gain) * 100)).toFixed(0)}%</span>
                  </div>
                  <div style={{ width: "100%", height: "6px", background: "rgba(255,255,255,0.1)", borderRadius: "3px", overflow: "hidden" }}>
                    <div style={{ width: `${Math.min(100, Math.max(0, (simulatorState.pnl / simulatorState.risk.stop_gain) * 100))}%`, height: "100%", background: "var(--success)" }}></div>
                  </div>
                </div>
                
                {/* Stop Loss Progress */}
                <div style={{ marginTop: "8px" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.7rem", opacity: 0.8, marginBottom: "4px" }}>
                    <span>Stop Loss (-${simulatorState.risk.stop_loss})</span>
                    <span>{Math.min(100, Math.max(0, (simulatorState.pnl / -simulatorState.risk.stop_loss) * 100)).toFixed(0)}%</span>
                  </div>
                  <div style={{ width: "100%", height: "6px", background: "rgba(255,255,255,0.1)", borderRadius: "3px", overflow: "hidden" }}>
                    <div style={{ width: `${Math.min(100, Math.max(0, (simulatorState.pnl / -simulatorState.risk.stop_loss) * 100))}%`, height: "100%", background: "var(--danger)" }}></div>
                  </div>
                </div>
              </div>
            )}
          </div>

          <div className="glass" style={{ padding: "20px", flex: 2, overflowY: "auto", maxHeight: "250px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
              <h3 style={{ margin: 0 }}>📋 Posições Abertas (SQLite DB)</h3>
              <div style={{ display: "flex", gap: "8px" }}>
                <button
                  onClick={() => handleManualTrade("CALL")}
                  disabled={executingTrade || !apiAuthToken || !Number.isFinite(Number(tradePreview?.atr)) || Number(tradePreview?.atr) <= 0}
                  style={{ background: "rgba(16,185,129,0.2)", color: "var(--success)", border: "1px solid var(--success)", padding: "4px 8px", borderRadius: "4px", fontSize: "0.75rem", cursor: executingTrade ? "wait" : "pointer", opacity: (!apiAuthToken || !Number.isFinite(Number(tradePreview?.atr)) || Number(tradePreview?.atr) <= 0) ? 0.5 : 1 }}
                  title={!apiAuthToken ? "Configure NEXT_PUBLIC_API_AUTH_TOKEN para habilitar." : (!Number.isFinite(Number(tradePreview?.atr)) || Number(tradePreview?.atr) <= 0 ? "ATR real indisponível para este ativo." : "")}
                >
                  {executingTrade ? "..." : "+ CALL (CQRS)"}
                </button>
                <button
                  onClick={() => handleManualTrade("PUT")}
                  disabled={executingTrade || !apiAuthToken || !Number.isFinite(Number(tradePreview?.atr)) || Number(tradePreview?.atr) <= 0}
                  style={{ background: "rgba(239,68,68,0.2)", color: "var(--danger)", border: "1px solid var(--danger)", padding: "4px 8px", borderRadius: "4px", fontSize: "0.75rem", cursor: executingTrade ? "wait" : "pointer", opacity: (!apiAuthToken || !Number.isFinite(Number(tradePreview?.atr)) || Number(tradePreview?.atr) <= 0) ? 0.5 : 1 }}
                  title={!apiAuthToken ? "Configure NEXT_PUBLIC_API_AUTH_TOKEN para habilitar." : (!Number.isFinite(Number(tradePreview?.atr)) || Number(tradePreview?.atr) <= 0 ? "ATR real indisponível para este ativo." : "")}
                >
                  {executingTrade ? "..." : "+ PUT (CQRS)"}
                </button>
              </div>
            </div>
            
            {cqrsTrades.length > 0 ? (
              <div style={{ marginBottom: "16px" }}>
                {cqrsTrades.map((t: any, idx: number) => (
                  <div key={idx} style={{ display: "flex", justifyContent: "space-between", padding: "8px 0", borderBottom: "1px solid rgba(255,255,255,0.1)" }}>
                    <span>
                      {t.direction === "CALL" ? "🟩 LONG" : "🟥 SHORT"}
                      <div style={{ fontSize: "0.75rem", opacity: 0.7 }}>Entry: {t.entry_price?.toFixed(2) ?? "0.00"}</div>
                      <div style={{ fontSize: "0.7rem", color: "var(--accent)" }}>{t.symbol} | SL: {t.sl?.toFixed(2)}</div>
                    </span>
                    <span style={{ textAlign: "right", color: "white", fontWeight: "bold" }}>
                      Qtd: {(t.qty ?? 0).toFixed(4)}
                      <div style={{ fontSize: "0.75rem", color: "white", opacity: 0.7, fontWeight: "normal" }}>Margem: ${(t.margin ?? 0).toFixed(2)}</div>
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <p style={{ opacity: 0.5, fontSize: "0.85rem", marginBottom: "16px" }}>Nenhuma posição registrada no SQLite.</p>
            )}

            
            <div>
              <strong style={{ fontSize: "0.85rem", opacity: 0.7 }}>HISTÓRICO</strong>
              {(simulatorState.history || []).length === 0 ? (
                <p style={{ opacity: 0.5, fontSize: "0.85rem" }}>Nenhuma operação finalizada ainda.</p>
              ) : (
                (simulatorState.history || []).map((t: any) => (
                  <div key={t.id} style={{ display: "flex", justifyContent: "space-between", padding: "8px 0", borderBottom: "1px solid rgba(255,255,255,0.1)" }}>
                    <span style={{ color: t.status === "WIN" ? "var(--success)" : (t.status === "LOSS" ? "var(--danger)" : "white") }}>
                      {t.status === "WIN" ? "📈" : (t.status === "LOSS" ? "📉" : "⚖️")} {t.direction} <span style={{fontSize:'0.7rem', opacity:0.5}}>[{t.strategy_info || "N/A"}]</span>
                    </span>
                    <span style={{ fontWeight: "bold", color: t.status === "WIN" ? "var(--success)" : (t.status === "LOSS" ? "var(--danger)" : "white") }}>
                      {(t.profit ?? 0) >= 0 ? "+" : ""}${(t.profit ?? 0).toFixed(2)}
                    </span>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
        )}
      </div>

      {/* Direita: Market Feed */}
      <div className="glass" style={{ padding: "20px", display: "flex", flexDirection: "column" }}>
        <h3 style={{ marginBottom: "16px", display: "flex", alignItems: "center" }}>
          <span className="live-indicator"></span> 
          Mercado Ao Vivo
        </h3>
        
        <div style={{ marginBottom: "24px" }}>
          <div style={{ fontSize: "0.8rem", opacity: 0.6, textTransform: "uppercase" }}>{activeSymbol} (Binance)</div>
          <div style={{ fontSize: "2.8rem", fontWeight: "bold" }}>
            {liveData.quote > 0 ? liveData.quote.toFixed(2) : "0.00"}
          </div>
        </div>

        <h4>Vela Atual (M{(activeConfig?.timeframe || 300) / 60})</h4>
        <div className="feed-section" style={{ marginTop: "12px" }}>
          {liveData.candle ? (
            <div className={`candle-card ${liveData.candle.close >= liveData.candle.open ? 'candle-bullish' : 'candle-bearish'}`}>
              <div>
                <div className="badge" style={{ 
                  background: liveData.candle.close >= liveData.candle.open ? 'var(--success-glow)' : 'var(--danger-glow)',
                  color: liveData.candle.close >= liveData.candle.open ? 'var(--bullish)' : 'var(--bearish)'
                }}>
                  {liveData.candle.close >= liveData.candle.open ? 'BULLISH' : 'BEARISH'}
                </div>
                <div style={{ marginTop: "8px", fontSize: "0.95rem" }}>O: {liveData.candle.open.toFixed(2)}</div>
                <div style={{ fontSize: "0.95rem" }}>C: {liveData.candle.close.toFixed(2)}</div>
              </div>
              <div style={{ textAlign: "right" }}>
                <div style={{ fontSize: "0.95rem" }}>H: {liveData.candle.high.toFixed(2)}</div>
                <div style={{ fontSize: "0.95rem" }}>L: {liveData.candle.low.toFixed(2)}</div>
              </div>
            </div>
          ) : (
            <p style={{ opacity: 0.5, fontSize: "0.9rem" }}>Aguardando sincronização da Binance...</p>
          )}
        </div>
        
        {/* AI Neural Feed Sidebar */}
        <div className="glass" style={{ marginTop: "24px", padding: "16px", display: "flex", flexDirection: "column", gap: "12px" }}>
          <h4 style={{ margin: 0, color: "var(--accent)", display: "flex", alignItems: "center", gap: "8px" }}>
            <span className={aiTaskState.status === "PROCESSING" ? "live-indicator" : ""} style={{
              background: aiTaskState.status === "PROCESSING" ? "var(--accent)" : "rgba(255,255,255,0.2)",
              animation: aiTaskState.status === "PROCESSING" ? "blink 1s infinite" : "none"
            }}></span>
            AI Neural Feed
          </h4>
          <div style={{ fontSize: "0.75rem", opacity: 0.6 }}>
            Telemetria ilustrativa: o backend ainda não expõe estado operacional real do pipeline de IA.
          </div>
          <div style={{ 
            background: "rgba(0,0,0,0.4)", 
            border: "1px solid rgba(255,255,255,0.05)", 
            borderRadius: "8px", 
            padding: "12px",
            fontFamily: "monospace",
            fontSize: "0.85rem",
            color: aiTaskState.status === "PROCESSING" ? "#60a5fa" : "#9ca3af",
            minHeight: "60px",
            display: "flex",
            alignItems: "center"
          }}>
            {aiTaskState.reason}
          </div>
        </div>
        <div 
          ref={chartContainerRef} 
          style={{ width: "100%", height: "250px", marginTop: "24px" }} 
        />
      </div>
    </div>
      ) : (
        <div style={{ flex: 1, overflow: 'auto', padding: '20px' }}>
          <div className="glass" style={{ padding: "30px", maxWidth: "1200px", margin: "0 auto" }}>
            <h2>Laboratório (Backtest Avançado) - {activeSymbol}</h2>
            <p style={{ opacity: 0.7 }}>Simule estratégias com a base histórica e veja os pontos de entrada (amostra de 1000 velas renderizadas no gráfico).</p>
            
            <div style={{ display: 'flex', gap: '16px', marginTop: '20px', alignItems: 'center' }}>
              <select 
                value={backtestStrategy} 
                onChange={(e) => setBacktestStrategy(e.target.value)}
                style={{ padding: '10px', background: 'rgba(0,0,0,0.5)', color: 'white', border: '1px solid rgba(255,255,255,0.2)', borderRadius: '4px' }}
              >
                <option value="Auto">✨ Auto-Otimização (I.A.)</option>
                <option value="Pin Bar">Pin Bar (Elite)</option>
                <option value="SMC">Smart Money Concepts</option>
                <option value="Bollinger">Bollinger Bands</option>
                <option value="3 Velas">3 Velas Consecutivas</option>
                <option value="EMA+MACD">EMA + MACD</option>
                <option value="SuperTrend">SuperTrend</option>
              </select>
              
              <select 
                value={backtestTimeframe} 
                onChange={(e) => setBacktestTimeframe(Number(e.target.value))}
                style={{ padding: '10px', background: 'rgba(0,0,0,0.5)', color: 'white', border: '1px solid rgba(255,255,255,0.2)', borderRadius: '4px' }}
              >
                <option value={60}>M1 (1 minuto)</option>
                <option value={300}>M5 (5 minutos)</option>
                <option value={900}>M15 (15 minutos)</option>
              </select>

              <select 
                value={backtestLimit} 
                onChange={(e) => setBacktestLimit(Number(e.target.value))}
                style={{ padding: '10px', background: 'rgba(0,0,0,0.5)', color: 'white', border: '1px solid rgba(255,255,255,0.2)', borderRadius: '4px' }}
              >
                <option value={1000}>1.000 Velas</option>
                <option value={5000}>5.000 Velas</option>
                <option value={10000}>10.000 Velas</option>
                <option value={50000}>50.000 Velas (Deep Test)</option>
              </select>

              <button 
                onClick={runAdvancedBacktest} 
                disabled={isBacktesting}
                style={{ background: "var(--accent)", color: "#000", border: "none", padding: "10px 24px", borderRadius: "4px", fontWeight: "bold", cursor: isBacktesting ? "not-allowed" : "pointer" }}
              >
                {isBacktesting ? "⏳ Processando..." : "▶️ Rodar Backtest"}
              </button>
            </div>
            
            {backtestResults && !backtestResults.error && (
              <div style={{ marginTop: "20px" }}>
                {backtestResults.optimal_strategy && (
                  <div style={{ marginBottom: "16px", background: "linear-gradient(90deg, rgba(255,193,7,0.2) 0%, rgba(255,152,0,0.2) 100%)", border: "1px solid rgba(255,193,7,0.5)", padding: "12px 16px", borderRadius: "8px", display: "flex", alignItems: "center", gap: "12px" }}>
                    <span style={{ fontSize: "1.5rem" }}>🏆</span>
                    <div>
                      <div style={{ fontWeight: "bold", color: "#FFC107" }}>Melhor Estratégia Encontrada</div>
                      <div style={{ opacity: 0.9, fontSize: "0.9rem" }}>O motor de I.A. testou todas as estratégias e elegeu <strong>{backtestResults.optimal_strategy}</strong> para as condições atuais.</div>
                    </div>
                  </div>
                )}
                <div style={{ display: "flex", gap: "16px" }}>
                 <div style={{ flex: 1, background: "rgba(0,0,0,0.3)", padding: "16px", borderRadius: "8px", textAlign: "center" }}>
                    <div style={{ opacity: 0.7, fontSize: "0.9rem" }}>Sinais Gerados</div>
                    <div style={{ fontSize: "1.5rem", fontWeight: "bold" }}>{backtestResults.signals}</div>
                 </div>
                 <div style={{ flex: 1, background: "rgba(0,0,0,0.3)", padding: "16px", borderRadius: "8px", textAlign: "center" }}>
                    <div style={{ opacity: 0.7, fontSize: "0.9rem" }}>Win Rate</div>
                    <div style={{ fontSize: "1.5rem", fontWeight: "bold", color: backtestResults.win_rate >= 50 ? "var(--success)" : "var(--danger)" }}>{backtestResults.win_rate}%</div>
                 </div>
                 <div style={{ flex: 1, background: "rgba(0,0,0,0.3)", padding: "16px", borderRadius: "8px", textAlign: "center" }}>
                    <div style={{ opacity: 0.7, fontSize: "0.9rem" }}>PnL (Lucro Estimado)</div>
                    <div style={{ fontSize: "1.5rem", fontWeight: "bold", color: backtestResults.pnl_usdt >= 0 ? "var(--success)" : "var(--danger)" }}>${backtestResults.pnl_usdt}</div>
                 </div>
                 <div style={{ flex: 1, background: "rgba(0,0,0,0.3)", padding: "16px", borderRadius: "8px", textAlign: "center" }}>
                    <div style={{ opacity: 0.7, fontSize: "0.9rem" }}>Wins / Losses</div>
                    <div style={{ fontSize: "1.5rem", fontWeight: "bold" }}>{backtestResults.wins} / {backtestResults.losses}</div>
                 </div>
              </div>
              </div>
            )}
            {backtestResults && backtestResults.error && (
              <div style={{ marginTop: "20px", color: "var(--danger)" }}>
                Erro: {backtestResults.error}
              </div>
            )}

            <div 
              ref={backtestChartContainerRef} 
              style={{ width: "100%", height: "400px", marginTop: "24px", background: "rgba(0,0,0,0.2)", borderRadius: "8px" }} 
            />
            
            {backtestResults && backtestResults.trades && backtestResults.trades.length > 0 && (
              <div style={{ marginTop: "24px" }}>
                <h3 style={{ marginBottom: "16px" }}>📝 Histórico de Operações</h3>
                <div style={{ background: "rgba(0,0,0,0.3)", borderRadius: "8px", overflow: "hidden" }}>
                  <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.9rem" }}>
                    <thead style={{ background: "rgba(255,255,255,0.05)", textAlign: "left" }}>
                      <tr>
                        <th style={{ padding: "12px", borderBottom: "1px solid rgba(255,255,255,0.1)" }}>Sinal</th>
                        <th style={{ padding: "12px", borderBottom: "1px solid rgba(255,255,255,0.1)" }}>Entrada (Data/Hora)</th>
                        <th style={{ padding: "12px", borderBottom: "1px solid rgba(255,255,255,0.1)" }}>Saída (Data/Hora)</th>
                        <th style={{ padding: "12px", borderBottom: "1px solid rgba(255,255,255,0.1)", textAlign: "right" }}>Preço Entrada</th>
                        <th style={{ padding: "12px", borderBottom: "1px solid rgba(255,255,255,0.1)", textAlign: "right" }}>Preço Saída</th>
                        <th style={{ padding: "12px", borderBottom: "1px solid rgba(255,255,255,0.1)", textAlign: "right" }}>Lucro (USDT)</th>
                        <th style={{ padding: "12px", borderBottom: "1px solid rgba(255,255,255,0.1)", textAlign: "right" }}>Saldo Acumulado</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(() => {
                        let acc = 0;
                        return backtestResults.trades.map((t: any, i: number) => {
                          acc += t.profit;
                          return (
                            <tr key={i} style={{ borderBottom: "1px solid rgba(255,255,255,0.05)" }}>
                              <td style={{ padding: "12px", color: t.signal === 'CALL' ? 'var(--success)' : 'var(--danger)', fontWeight: 'bold' }}>
                                {t.signal === 'CALL' ? '🔼 COMPRA' : '🔽 VENDA'}
                              </td>
                              <td style={{ padding: "12px" }}>{new Date(t.entry_time * 1000).toLocaleString()}</td>
                              <td style={{ padding: "12px" }}>{new Date(t.exit_time * 1000).toLocaleString()}</td>
                              <td style={{ padding: "12px", textAlign: "right" }}>${t.entry_price.toFixed(2)}</td>
                              <td style={{ padding: "12px", textAlign: "right" }}>${t.exit_price.toFixed(2)}</td>
                              <td style={{ padding: "12px", textAlign: "right", color: t.profit > 0 ? 'var(--success)' : 'var(--danger)', fontWeight: 'bold' }}>
                                {t.profit > 0 ? '+' : ''}{t.profit.toFixed(2)}
                              </td>
                              <td style={{ padding: "12px", textAlign: "right", color: acc > 0 ? 'var(--success)' : 'var(--danger)', fontWeight: 'bold' }}>
                                ${acc.toFixed(2)}
                              </td>
                            </tr>
                          );
                        });
                      })()}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
    </ErrorBoundary>
  );
}
