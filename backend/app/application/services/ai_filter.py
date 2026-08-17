import os
import logging
import json
import asyncio
from typing import List
from openai import AsyncOpenAI
import pandas as pd

logger = logging.getLogger(__name__)

class AIFilter:
    def __init__(self):
        self.api_key = os.getenv("MANIFEST_API_KEY", os.getenv("OPENAI_API_KEY"))
        self.base_url = os.getenv("MANIFEST_BASE_URL", "https://api.openai.com/v1")
        self.model = os.getenv("MANIFEST_MODEL_NAME", "gpt-4o-mini")
        
        if self.api_key:
            self.client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
        else:
            self.client = None
            logger.warning("Nenhuma API Key de IA configurada. AI Filter estara inativo.")

    async def make_decision(self, df: pd.DataFrame, strategy_name: str) -> dict:
        """
        Analisa o contexto técnico e decide se entra ou espera.
        Retorna dicionário: {"decision": "BUY/SELL/WAIT", "reason": str, "confidence": float}
        """
        if not self.client or df.empty or len(df) < 20:
            return {"decision": "WAIT", "reason": "Sem contexto suficiente ou IA inativa", "confidence": 0.0}

        try:
            recent = df.iloc[-20:]
            last_row = df.iloc[-1]
            context_str = (
                "Últimas 20 velas (O, H, L, C):\n" +
                "\n".join([f"- O:{r['open']:.2f} H:{r['high']:.2f} L:{r['low']:.2f} C:{r['close']:.2f}" for _, r in recent.iterrows()]) +
                f"\nIndicadores: RSI:{last_row.get('RSI_14', 50):.2f} | "
                f"EMA20:{last_row.get('EMA_20', 0):.2f} | EMA50:{last_row.get('EMA_50', 0):.2f} | "
                f"EMA200:{last_row.get('EMA_200', 0):.2f} | ATR:{last_row.get('ATRr_14', 0):.2f}"
            )

            prompt = (
                f"Voce é um especialista em trading de cripto. Analise o contexto: '{strategy_name}'.\n"
                f"{context_str}\n"
                f"REGRA RÍGIDA DE TENDÊNCIA (EMA200):\n"
                f"1. Se o Preço < EMA200, NUNCA dê BUY. Priorize apenas SELL.\n"
                f"2. Se o Preço > EMA200, NUNCA dê SELL. Priorize apenas BUY.\n"
                f"Analise o Price Action e RSI. Se o sinal violar a tendência da EMA200, dê WAIT.\n"
                f"Responda APENAS no formato JSON: \n"
                f"{{\"decision\": \"BUY\" | \"SELL\" | \"WAIT\", \"reason\": \"sua justificativa curta\", \"confidence\": 0.0-1.0}}"
            )

            # O modelo de raciocínio (mimo-v2.5-pro) às vezes gasta todos os tokens
            # no raciocínio e devolve content vazio. Tentamos de novo (com uma
            # pequena espera) antes de desistir.
            content = ""
            for attempt in range(3):
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "system", "content": "Você é um bot de trading preciso."}, {"role": "user", "content": prompt}],
                    temperature=0.0,
                    max_tokens=1024
                )
                content = (response.choices[0].message.content or "").replace("```json", "").replace("```", "").strip()
                if content:
                    break
                logger.warning(f"Resposta vazia da IA (tentativa {attempt + 1}/3). Re-tentando...")
                await asyncio.sleep(1.0)

            if not content:
                logger.warning(f"Resposta da IA vazia. Contexto enviado: {context_str[:200]}...")
                return {"decision": "WAIT", "reason": "Resposta vazia da IA", "confidence": 0.0}


            # Extrai o primeiro objeto JSON { ... } — o modelo pode adicionar texto
            # antes/depois do JSON (explicações, múltiplos objetos, etc.).
            start = content.find("{")
            end = content.rfind("}")
            if start == -1 or end <= start:
                raise ValueError(f"Resposta sem JSON válido: {content[:200]!r}")

            result = json.loads(content[start:end + 1])

            # Sanitiza o resultado — garante as chaves esperadas e o range de confiança.
            decision = str(result.get("decision", "WAIT")).upper()
            if decision not in ("BUY", "SELL", "WAIT"):
                decision = "WAIT"
            confidence = float(result.get("confidence", 0.0) or 0.0)
            confidence = max(0.0, min(1.0, confidence))
            return {
                "decision": decision,
                "reason": str(result.get("reason", "")),
                "confidence": confidence,
            }
        except Exception as e:
            logger.error(f"Erro na decisão da IA: {e}")
            return {"decision": "WAIT", "reason": "Erro na IA", "confidence": 0.0}
