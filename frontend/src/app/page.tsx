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
  const [activeConfig, setActiveConfig] = useState<any>({ timeframe: 300, strategy: "EMA+MACD" });
  const [autoOptimize, setAutoOptimize] = useState<boolean>(false);
  const [simulatorState, setSimulatorState] = useState<any>(null);
  const [newsStatus, setNewsStatus] = useState<any>(null);
  const [portfolio, setPortfolio] = useState<any>(null);
  const [activeSymbol, setActiveSymbol] = useState<string>("BTC/USDT");
  const [tradePreview, setTradePreview] = useState<any>(null);

  // Backtest State
  const [currentView, setCurrentView] = useState<"dashboard" | "backtest" | "config">("dashboard");
  const [backtestResults, setBacktestResults] = useState<any>(null);
  const [isBacktesting, setIsBacktesting] = useState(false);
  const [backtestStrategy, setBacktestStrategy] = useState("Auto");

  // Risk Settings State
  const [riskStake, setRiskStake] = useState<number>(10);
  const [riskGale, setRiskGale] = useState<number>(2);
  const [riskStopLoss, setRiskStopLoss] = useState<number>(50);
  const [riskStopGain, setRiskStopGain] = useState<number>(50);
  const [isSavingRisk, setIsSavingRisk] = useState<boolean>(false);

  const [backtestTimeframe, setBacktestTimeframe] = useState(300);
  const [backtestLimit, setBacktestLimit] = useState(1000);

  const backtestChartContainerRef = useRef<HTMLDivElement>(null);
  const backtestChartRef = useRef<any>(null);
  const backtestSeriesRef = useRef<any>(null);

  const activeSymbolRef = useRef(activeSymbol);
  useEffect(() => {
    activeSymbolRef.current = activeSymbol;
  }, [activeSymbol]);

  const ws = useRef<WebSocket | null>(null);
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartSeriesRef = useRef<any>(null);
  const priceLinesRef = useRef<any[]>([]);

  useEffect(() => {
    // Connect to WebSocket
    const wsUrl = process.env.NEXT_PUBLIC_BACKEND_WS_URL || `ws://${window.location.hostname}:${process.env.NEXT_PUBLIC_API_PORT || 8000}/ws`;
    ws.current = new WebSocket(wsUrl);

    ws.current.onopen = () => {
      console.log("Connected to backend WS");
      ws.current?.send(JSON.stringify({ command: "WATCH_SYMBOL", symbol: activeSymbolRef.current }));
    };

    ws.current.onmessage = (event) => {
      const msg = JSON.parse(event.data);

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
        if (chartSeriesRef.current) {
          chartSeriesRef.current.main.setData(msg.data);
          // Popula os novos indicadores
          const volumeData: any[] = [];
          const bbUpperData: any[] = [];
          const bbMiddleData: any[] = [];
          const bbLowerData: any[] = [];
          const macdLineData: any[] = [];
          const macdSignalData: any[] = [];
          const macdHistData: any[] = [];

          msg.data.forEach((item: any) => {
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

          if (chartSeriesRef.current.volume && volumeData.length > 0) chartSeriesRef.current.volume.setData(volumeData);
          if (chartSeriesRef.current.bb.upper && bbUpperData.length > 0) chartSeriesRef.current.bb.upper.setData(bbUpperData);
          if (chartSeriesRef.current.bb.middle && bbMiddleData.length > 0) chartSeriesRef.current.bb.middle.setData(bbMiddleData);
          if (chartSeriesRef.current.bb.lower && bbLowerData.length > 0) chartSeriesRef.current.bb.lower.setData(bbLowerData);
          if (chartSeriesRef.current.macd.line && macdLineData.length > 0) chartSeriesRef.current.macd.line.setData(macdLineData);
          if (chartSeriesRef.current.macd.signal && macdSignalData.length > 0) chartSeriesRef.current.macd.signal.setData(macdSignalData);
          if (chartSeriesRef.current.macd.hist && macdHistData.length > 0) chartSeriesRef.current.macd.hist.setData(macdHistData);
        }
      }
    };

    return () => {
      if (ws.current) ws.current.close();
    };
  }, []);

  useEffect(() => {
    const fetchPortfolio = async () => {
      try {
        const httpUrl = process.env.NEXT_PUBLIC_BACKEND_HTTP_URL || `http://${window.location.hostname}:${process.env.NEXT_PUBLIC_API_PORT || 8000}`;
        const res = await fetch(`${httpUrl}/portfolio`);
        const data = await res.json();
        setPortfolio(data);
      } catch (e) {}
    };
    fetchPortfolio();
    const interval = setInterval(fetchPortfolio, 5000);

    // Fetch Risk Settings
    const fetchRisk = async () => {
      try {
        const httpUrl = process.env.NEXT_PUBLIC_BACKEND_HTTP_URL || `http://${window.location.hostname}:${process.env.NEXT_PUBLIC_API_PORT || 8000}`;
        const res = await fetch(`${httpUrl}/api/risk_settings`);
        const data = await res.json();
        setRiskStake(data.stake_initial);
        setRiskGale(data.max_gale);
        setRiskStopLoss(data.daily_stop_loss);
        setRiskStopGain(data.daily_stop_gain);
      } catch (e) {}
    };
    fetchRisk();

    return () => clearInterval(interval);
  }, []);

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
      height: 500,
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
    chartSeriesRef.current = { main: candlestickSeries };

    // --- PAINEL DE VOLUME (EMBAIXO) ---
    const volumeSeries = chart.addSeries(HistogramSeries, {
      priceFormat: { type: 'volume' },
      priceScaleId: 'volume',
    });
    chart.priceScale("volume").applyOptions({
      scaleMargins: { top: 0.8, bottom: 0 },
    });
    chartSeriesRef.current.volume = volumeSeries;

    // --- PAINEL DE MACD (MEIO) ---
    const macdLineSeries = chart.addSeries(LineSeries, { color: '#2962FF', lineWidth: 1, priceScaleId: 'macd' });
    chart.priceScale('macd').applyOptions({
      scaleMargins: { top: 0.6, bottom: 0.2 },
    });
    const macdSignalSeries = chart.addSeries(LineSeries, { color: '#FF6D00', lineWidth: 1, priceScaleId: 'macd' });
    const macdHistSeries = chart.addSeries(HistogramSeries, { priceScaleId: 'macd' });
    chartSeriesRef.current.macd = {
        line: macdLineSeries,
        signal: macdSignalSeries,
        hist: macdHistSeries
    };

    // --- BANDAS DE BOLLINGER (NO GRÁFICO PRINCIPAL) ---
    const bbUpperSeries = chart.addSeries(LineSeries, { color: 'rgba(33, 150, 243, 0.4)', lineWidth: 1 });
    const bbMiddleSeries = chart.addSeries(LineSeries, { color: 'rgba(255, 152, 0, 0.4)', lineWidth: 1 });
    const bbLowerSeries = chart.addSeries(LineSeries, { color: 'rgba(33, 150, 243, 0.4)', lineWidth: 1 });
    chartSeriesRef.current.bb = {
        upper: bbUpperSeries,
        middle: bbMiddleSeries,
        lower: bbLowerSeries
    };


    const handleResize = () => {
      if (chartContainerRef.current) {
        chart.applyOptions({ width: chartContainerRef.current.clientWidth });
      }
    };

    window.addEventListener('resize', handleResize);
    return () => {
      window.removeEventListener('resize', handleResize);
      chart.remove();
    };
  }, [currentView, activeSymbol]);

  useEffect(() => {
    const httpUrl = process.env.NEXT_PUBLIC_BACKEND_HTTP_URL || `http://${window.location.hostname}:${process.env.NEXT_PUBLIC_API_PORT || 8000}`;
    const fetchChartHistory = async () => {
      try {
        const res = await fetch(`${httpUrl}/api/chart_history?symbol=${activeSymbol}&limit=200`);
        const result = await res.json();
        if (chartSeriesRef.current && result.data) {
          chartSeriesRef.current.main.setData(result.data);

          // Popula os novos indicadores
          const volumeData: any[] = [];
          const bbUpperData: any[] = [];
          const bbMiddleData: any[] = [];
          const bbLowerData: any[] = [];
          const macdLineData: any[] = [];
          const macdSignalData: any[] = [];
          const macdHistData: any[] = [];

          result.data.forEach((item: any) => {
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

          if (chartSeriesRef.current.volume && volumeData.length > 0) chartSeriesRef.current.volume.setData(volumeData);
          if (chartSeriesRef.current.bb.upper && bbUpperData.length > 0) chartSeriesRef.current.bb.upper.setData(bbUpperData);
          if (chartSeriesRef.current.bb.middle && bbMiddleData.length > 0) chartSeriesRef.current.bb.middle.setData(bbMiddleData);
          if (chartSeriesRef.current.bb.lower && bbLowerData.length > 0) chartSeriesRef.current.bb.lower.setData(bbLowerData);
          if (chartSeriesRef.current.macd.line && macdLineData.length > 0) chartSeriesRef.current.macd.line.setData(macdLineData);
          if (chartSeriesRef.current.macd.signal && macdSignalData.length > 0) chartSeriesRef.current.macd.signal.setData(macdSignalData);
          if (chartSeriesRef.current.macd.hist && macdHistData.length > 0) chartSeriesRef.current.macd.hist.setData(macdHistData);
        }
      } catch (e) {
        console.error("Failed to fetch chart history", e);
      }
    };

    fetchChartHistory();
    const interval = setInterval(fetchChartHistory, 300000); // Refetch every 5 minutes
    return () => clearInterval(interval);
  }, [activeSymbol]);

  useEffect(() => {
    if (chartSeriesRef.current && currentView === 'dashboard' && liveData.candle) {
        const candleData = {
            time: liveData.candle.epoch,
            open: liveData.candle.open,
            high: liveData.candle.high,
            low: liveData.candle.low,
            close: liveData.candle.close,
        };
        try {
            chartSeriesRef.current.main.update(candleData);

            if(liveData.candle.indicators) {
                const indicators = liveData.candle.indicators;
                if (chartSeriesRef.current.volume) {
                    chartSeriesRef.current.volume.update({ time: candleData.time, value: liveData.candle.volume, color: candleData.close >= candleData.open ? 'rgba(38, 166, 154, 0.5)' : 'rgba(239, 83, 80, 0.5)' });
                }
                if (chartSeriesRef.current.bb.upper) {
                    chartSeriesRef.current.bb.upper.update({ time: candleData.time, value: indicators.BBU_21_2_0 });
                }
                if (chartSeriesRef.current.bb.middle) {
                    chartSeriesRef.current.bb.middle.update({ time: candleData.time, value: indicators.BBM_21_2_0 });
                }
                if (chartSeriesRef.current.bb.lower) {
                    chartSeriesRef.current.bb.lower.update({ time: candleData.time, value: indicators.BBL_21_2_0 });
                }
                if (chartSeriesRef.current.macd.line) {
                    chartSeriesRef.current.macd.line.update({ time: candleData.time, value: indicators.MACD_12_26_9 });
                }
                if (chartSeriesRef.current.macd.signal) {
                    chartSeriesRef.current.macd.signal.update({ time: candleData.time, value: indicators.MACDs_12_26_9 });
                }
                if (chartSeriesRef.current.macd.hist) {
                    chartSeriesRef.current.macd.hist.update({ time: candleData.time, value: indicators.MACDh_12_26_9, color: indicators.MACDh_12_26_9 >= 0 ? '#26a69a' : '#ef5350' });
                }
            }

        } catch (e) {
            console.warn("Ignoring tick update error (possibly older timestamp)", e);
        }
    }
  }, [liveData, currentView]);

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

  const handleSetConfig = (timeframe: number, strategy: string) => {
    if (ws.current) {
      ws.current.send(JSON.stringify({ command: "SET_ACTIVE_CONFIG", config: { timeframe, strategy } }));
    }
  };

  const handleToggleAutoOptimize = () => {
    if (ws.current) {
      ws.current.send(JSON.stringify({ command: "TOGGLE_AUTO_OPTIMIZE" }));
    }
  };

  const handleToggleGlobalMutant = () => {
    if (ws.current) {
      ws.current.send(JSON.stringify({ command: "TOGGLE_GLOBAL_MUTANT" }));
    }
  };

  const handleRunBacktest = async () => {
    setIsBacktesting(true);
    try {
      const httpUrl = process.env.NEXT_PUBLIC_BACKEND_HTTP_URL || `http://${window.location.hostname}:${process.env.NEXT_PUBLIC_API_PORT || 8000}`;
      const response = await fetch(`${httpUrl}/api/backtest`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ symbol: activeSymbol, strategy: backtestStrategy, timeframe: backtestTimeframe, limit: backtestLimit }),
      });
      const data = await response.json();
      setBacktestResults(data);

      // Limpar os marcadores antigos e adicionar os novos
      if (backtestChartRef.current && backtestSeriesRef.current) {
        const main = backtestSeriesRef.current.main;
        const volume = backtestSeriesRef.current.volume;
        const bb = backtestSeriesRef.current.bb;
        const macd = backtestSeriesRef.current.macd;

        main.setData(data.history);

        const volumeData: any[] = [];
        const bbUpperData: any[] = [];
        const bbMiddleData: any[] = [];
        const bbLowerData: any[] = [];
        const macdLineData: any[] = [];
        const macdSignalData: any[] = [];
        const macdHistData: any[] = [];

        data.history.forEach((item: any) => {
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

        if (volumeData.length > 0) volume.setData(volumeData);
        if (bbUpperData.length > 0) bb.upper.setData(bbUpperData);
        if (bbMiddleData.length > 0) bb.middle.setData(bbMiddleData);
        if (bbLowerData.length > 0) bb.lower.setData(bbLowerData);
        if (macdLineData.length > 0) macd.line.setData(macdLineData);
        if (macdSignalData.length > 0) macd.signal.setData(macdSignalData);
        if (macdHistData.length > 0) macd.hist.setData(macdHistData);

        if (data.trades) { // Alterado de backtestResults.trades para data.trades
          const markers = data.trades.map((t: any) => ({ // Alterado de backtestResults.trades para data.trades
            time: t.entry_time,
            position: t.signal === 'CALL' ? 'belowBar' : 'aboveBar',
            color: t.signal === 'CALL' ? '#26a69a' : '#ef5350',
            shape: t.signal === 'CALL' ? 'arrowUp' : 'arrowDown',
            text: `${t.signal} (${t.profit > 0 ? '+' : ''}${t.profit.toFixed(2)})`
          }));

          const uniqueMarkers: any[] = [];
          const seenTimes = new Set();
          markers.sort((a: any, b: any) => a.time - b.time).forEach((m: any) => {
            if (!seenTimes.has(m.time)) {
              seenTimes.add(m.time);
              uniqueMarkers.push(m);
            }
          });

          main.setMarkers(uniqueMarkers.length > 0 ? uniqueMarkers : []);
        } else {
            main.setMarkers([]);
        }
    }
    } catch (err) {
        console.error("Erro ao definir dados/marcadores do backtest no gráfico:", err);
    } finally { // Adicionado finally para garantir que o isBacktesting seja false
        setIsBacktesting(false);
    }
  };

  const handleSaveRiskSettings = async () => {
    setIsSavingRisk(true);
    try {
      const httpUrl = process.env.NEXT_PUBLIC_BACKEND_HTTP_URL || `http://${window.location.hostname}:${process.env.NEXT_PUBLIC_API_PORT || 8000}`;
      await fetch(`${httpUrl}/api/risk_settings`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          stake_initial: riskStake,
          max_gale: riskGale,
          daily_stop_loss: riskStopLoss,
          daily_stop_gain: riskStopGain,
        }),
      });
      alert("Configurações de risco salvas com sucesso!");
    } catch (e) {
      console.error("Failed to save risk settings", e);
      alert("Erro ao salvar configurações de risco.");
    } finally {
      setIsSavingRisk(false);
    }
  };

  // Efeito para CRIAR o gráfico de backtest
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
      height: 500,
      timeScale: {
        timeVisible: true,
        secondsVisible: false,
      }
    });

    // --- GRÁFICO PRINCIPAL ---
    const candlestickSeries = chart.addSeries(CandlestickSeries, {
        upColor: '#26a69a',
        downColor: '#ef5350',
        borderVisible: false,
        wickUpColor: '#26a69a',
        wickDownColor: '#ef5350',
    });

    // --- BANDAS DE BOLLINGER (NO GRÁFICO PRINCIPAL) ---
    const bbUpperSeries = chart.addSeries(LineSeries, { color: 'rgba(33, 150, 243, 0.4)', lineWidth: 1, crosshairMarkerVisible: false, lastValueVisible: false });
    const bbMiddleSeries = chart.addSeries(LineSeries, { color: 'rgba(255, 152, 0, 0.4)', lineWidth: 1, crosshairMarkerVisible: false, lastValueVisible: false });
    const bbLowerSeries = chart.addSeries(LineSeries, { color: 'rgba(33, 150, 243, 0.4)', lineWidth: 1, crosshairMarkerVisible: false, lastValueVisible: false });

    // --- PAINEL DE VOLUME (EMBAIXO) ---
    const volumeSeries = chart.addSeries(HistogramSeries, {
      priceFormat: { type: 'volume' },
      priceScaleId: 'volume',
    });
    chart.priceScale('volume').applyOptions({
      scaleMargins: { top: 0.8, bottom: 0 }, // Ocupa os 20% inferiores
    });

    // --- PAINEL DE MACD (MEIO) ---
    const macdLineSeries = chart.addSeries(LineSeries, { color: '#2962FF', lineWidth: 1, priceScaleId: 'macd', crosshairMarkerVisible: false, lastValueVisible: false });
    chart.priceScale('macd').applyOptions({
      scaleMargins: { top: 0.6, bottom: 0.2 }, // Entre 60% e 80% do topo
    });
    const macdSignalSeries = chart.addSeries(LineSeries, { color: '#FF6D00', lineWidth: 1, priceScaleId: 'macd', crosshairMarkerVisible: false, lastValueVisible: false });
    const macdHistSeries = chart.addSeries(HistogramSeries, { priceScaleId: 'macd' });

    backtestSeriesRef.current = {
      main: candlestickSeries,
      volume: volumeSeries,
      bb: {
        upper: bbUpperSeries,
        middle: bbMiddleSeries,
        lower: bbLowerSeries
      },
      macd: {
        line: macdLineSeries,
        signal: macdSignalSeries,
        hist: macdHistSeries
      }
    };

    backtestChartRef.current = chart;

    const handleResize = () => {
      if (backtestChartContainerRef.current) {
        backtestChartRef.current.applyOptions({ width: backtestChartContainerRef.current.clientWidth });
      }
    };

    window.addEventListener('resize', handleResize);
    return () => {
      window.removeEventListener('resize', handleResize);
      if (backtestChartRef.current) backtestChartRef.current.remove();
    };
  }, [currentView, activeSymbol]);


  return (
    <ErrorBoundary>
      <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', background: '#111', color: 'white', padding: '20px' }}>
        <header style={{ marginBottom: '20px' }}>
          <h1>Mutant Crypto Bot</h1>
          <nav>
            <button onClick={() => setCurrentView('dashboard')} style={{ margin: '0 5px', padding: '8px 15px', background: currentView === 'dashboard' ? 'lightblue' : '#333', border: 'none', borderRadius: '5px', color: 'white' }}>Dashboard</button>
            <button onClick={() => setCurrentView('backtest')} style={{ margin: '0 5px', padding: '8px 15px', background: currentView === 'backtest' ? 'lightblue' : '#333', border: 'none', borderRadius: '5px', color: 'white' }}>Backtest</button>
            <button onClick={() => setCurrentView('config')} style={{ margin: '0 5px', padding: '8px 15px', background: currentView === 'config' ? 'lightblue' : '#333', border: 'none', borderRadius: '5px', color: 'white' }}>Configuração</button>
          </nav>
        </header>

        {currentView === 'dashboard' && (
          <div>
            <h2>Dashboard</h2>
            {/* Botões das moedas disponíveis */}
            <div style={{ display: 'flex', gap: '10px', marginBottom: '20px' }}>
              {["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT"].map(sym => (
                <button
                  key={sym}
                  onClick={() => handleChangeSymbol(sym)}
                  style={{
                    padding: '10px 15px',
                    background: activeSymbol === sym ? 'lightgreen' : '#444',
                    border: 'none',
                    borderRadius: '5px',
                    color: 'white',
                    cursor: 'pointer'
                  }}
                >
                  {sym}
                </button>
              ))}
            </div>

            {/* Placeholder para o gráfico */}
            <div ref={chartContainerRef} style={{ width: '100%', height: '400px', background: '#222', marginBottom: '20px' }}></div>

            {/* Exemplo de dados ao vivo */}
            <h3>Dados Atuais ({activeSymbol})</h3>
            <p>Cotação: {liveData.quote > 0 ? liveData.quote.toFixed(2) : "0.00"}</p>
            <p>Vela: {liveData.candle ? `O:${liveData.candle.open.toFixed(2)} C:${liveData.candle.close.toFixed(2)}` : "Aguardando..."}</p>
          </div>
        )}

        {currentView === 'backtest' && (
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
                  <option value="Bollinger">Bollinger Bands</option>
                  <option value="EMA+MACD">EMA + MACD</option>
                  <option value="Bollinger+EMA+MACD">📈 Combo Bollinger+EMA+MACD</option>
                  <option value="Triple Confluence">🏆 Triple Confluence (Padrão)</option>
                </select>

                <select
                  value={backtestTimeframe}
                  onChange={(e) => setBacktestTimeframe(Number(e.target.value))}
                  style={{ padding: '10px', background: 'rgba(0,0,0,0.5)', color: 'white', border: '1px solid rgba(255,255,255,0.2)', borderRadius: '4px' }}
                >
                  <option value={60}>M1</option>
                  <option value={300}>M5</option>
                  <option value={900}>M15</option>
                </select>

                <select
                  value={backtestLimit}
                  onChange={(e) => setBacktestLimit(Number(e.target.value))}
                  style={{ padding: '10px', background: 'rgba(0,0,0,0.5)', color: 'white', border: '1px solid rgba(255,255,255,0.2)', borderRadius: '4px' }}
                >
                  <option value={500}>Últimas 500 Velas</option>
                  <option value={1000}>Últimas 1000 Velas</option>
                  <option value={2000}>Últimas 2000 Velas</option>
                </select>

                <button onClick={handleRunBacktest} disabled={isBacktesting} style={{ padding: '10px 20px', background: isBacktesting ? '#555' : 'var(--accent)', color: isBacktesting ? '#999' : '#000', border: 'none', borderRadius: '4px', fontWeight: 'bold', cursor: isBacktesting ? 'not-allowed' : 'pointer' }}>
                  {isBacktesting ? "Executando..." : "Executar Simulação"}
                </button>
              </div>

              <div ref={backtestChartContainerRef} style={{ width: '100%', height: '500px', marginTop: '30px' }} />

              {backtestResults && (
                <div style={{ marginTop: '30px', background: 'rgba(255,255,255,0.05)', padding: '20px', borderRadius: '8px' }}>
                  <h3>Resultados da Simulação</h3>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '20px' }}>
                    <div><strong>Total de Trades:</strong> {backtestResults.stats.total_trades}</div>
                    <div><strong>Trades Vencedores:</strong> {backtestResults.stats.winning_trades}</div>
                    <div><strong>Trades Perdedores:</strong> {backtestResults.stats.losing_trades}</div>
                    <div><strong>Win Rate:</strong> {backtestResults.stats.win_rate.toFixed(2)}%</div>
                    <div><strong>PnL Total (USDT):</strong> <span style={{ color: backtestResults.stats.pnl_usdt > 0 ? 'var(--success)' : 'var(--danger)' }}>{backtestResults.stats.pnl_usdt.toFixed(2)}</span></div>
                    <div><strong>Maior Ganho:</strong> {backtestResults.stats.max_profit.toFixed(2)}</div>
                    <div><strong>Maior Perda:</strong> {backtestResults.stats.max_loss.toFixed(2)}</div>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {currentView === 'config' && (
          <div style={{ flex: 1, overflow: 'auto', padding: '20px' }}>
            <div className="glass" style={{ padding: "30px", maxWidth: "800px", margin: "0 auto" }}>
              <h2>Configurações Globais de Risco</h2>
              <p style={{ opacity: 0.7 }}>Ajustes que afetam o gerenciamento de risco de todos os robôs.</p>

              <div style={{ marginTop: "30px", display: "grid", gridTemplateColumns: "1fr 1fr", gap: "24px" }}>
                <div>
                  <label style={{ display: 'block', marginBottom: '8px', opacity: 0.8 }}>Margem por Trade ($)</label>
                  <input type="number" value={riskStake} onChange={e => setRiskStake(Number(e.target.value))}
                    style={{ width: '100%', padding: '12px', background: 'rgba(0,0,0,0.5)', color: 'white', border: '1px solid rgba(255,255,255,0.2)', borderRadius: '4px' }}
                  />
                </div>
                <div>
                  <label style={{ display: 'block', marginBottom: '8px', opacity: 0.8 }}>Ciclos de Gale (Máx)</label>
                  <input type="number" value={riskGale} onChange={e => setRiskGale(Number(e.target.value))}
                    style={{ width: '100%', padding: '12px', background: 'rgba(0,0,0,0.5)', color: 'white', border: '1px solid rgba(255,255,255,0.2)', borderRadius: '4px' }}
                  />
                </div>
                <div>
                  <label style={{ display: 'block', marginBottom: '8px', opacity: 0.8 }}>Stop Gain Diário ($)</label>
                  <input type="number" value={riskStopGain} onChange={e => setRiskStopGain(Number(e.target.value))}
                    style={{ width: '100%', padding: '12px', background: 'rgba(0,0,0,0.5)', color: 'white', border: '1px solid rgba(255,255,255,0.2)', borderRadius: '4px' }}
                  />
                </div>
                <div>
                  <label style={{ display: 'block', marginBottom: '8px', opacity: 0.8 }}>Stop Loss Diário ($)</label>
                  <input type="number" value={riskStopLoss} onChange={e => setRiskStopLoss(Number(e.target.value))}
                    style={{ width: '100%', padding: '12px', background: 'rgba(0,0,0,0.5)', color: 'white', border: '1px solid rgba(255,255,255,0.2)', borderRadius: '4px' }}
                  />
                </div>
              </div>

              <div style={{ marginTop: '30px', textAlign: 'right' }}>
                <button onClick={handleSaveRiskSettings} disabled={isSavingRisk} style={{ padding: '12px 24px', background: isSavingRisk ? '#555' : 'var(--accent)', color: '#000', border: 'none', borderRadius: '4px', fontWeight: 'bold', cursor: 'pointer' }}>
                  {isSavingRisk ? 'Salvando...' : 'Salvar Configurações'}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </ErrorBoundary>
  );
}