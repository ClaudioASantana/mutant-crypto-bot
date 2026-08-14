import os
import logging
from typing import List
from openai import AsyncOpenAI
import pandas as pd
from app.models.market import Candle

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

    async def evaluate_signal(self, df: pd.DataFrame, signal_direction: str, strategy_name: str) -> bool:
        """
        Usa LLM para avaliar se um sinal tecnico faz sentido no contexto macro das ultimas velas.
        Retorna True se aprovado, False se rejeitado (ou se a IA falhar).
        """
        if not self.client or df.empty or len(df) < 5:
            # Fallback seguro: se não tiver IA, aprova o sinal técnico
            return True
            
        try:
            # Pega as últimas 5 velas para dar contexto ao LLM
            recent = df.iloc[-5:]
            context_str = "Últimas 5 velas (Open, High, Low, Close, Volume):\n"
            for idx, row in recent.iterrows():
                context_str += f"- O:{row['open']} H:{row['high']} L:{row['low']} C:{row['close']} V:{row['volume']}\n"
                
            prompt = (
                f"Voce é um analista quantitativo focado em criptomoedas.\n"
                f"Uma estrategia chamada '{strategy_name}' gerou um sinal de '{signal_direction}'.\n"
                f"Aqui esta a acao do preco recente:\n{context_str}\n"
                f"Considere a estrutura geral, padrões harmônicos de mercado (ex: ABCD / pullbacks) e momento.\n"
                f"Baseado puramente no Price Action e Volume, voce aprova esta entrada? "
                f"Responda APENAS 'SIM' ou 'NAO'."
            )
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Você avalia sinais de trading de forma objetiva."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0,
                max_tokens=10
            )
            
            content = response.choices[0].message.content
            if not content:
                content = "SIM"
            answer = content.strip().upper()
            if "SIM" in answer:
                return True
            elif "NAO" in answer or "NÃO" in answer:
                logger.info(f"Sinal {signal_direction} rejeitado pela IA.")
                return False
            return True
            
        except Exception as e:
            logger.error(f"Erro ao avaliar sinal com IA: {e}")
            return True
