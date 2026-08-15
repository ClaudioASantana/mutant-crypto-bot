import os
from pydantic import BaseModel
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from app.rag.vector import get_vector_store
from app.models.market import Signal, SignalType
from app.services.llm_throttle import llm_rate_limiter, llm_retry, OpenAIRateLimitError
import logging

logger = logging.getLogger(__name__)
load_dotenv()

BASE_URL = os.getenv("MANIFEST_BASE_URL")
API_KEY = os.getenv("MANIFEST_API_KEY")
MODEL_NAME = os.getenv("MANIFEST_MODEL_NAME")

llm = ChatOpenAI(
    openai_api_base=BASE_URL,
    openai_api_key=API_KEY,
    model=MODEL_NAME,
    temperature=0.0
)

# Initialize vector store connection
vector_store = get_vector_store()
retriever = vector_store.as_retriever(search_kwargs={"k": 3})

system_prompt = """Você é o Copiloto Explicativo de um robô de opções binárias.
Sua função não é decidir se o trade deve ser feito, pois o motor matemático (cockpit) já fez isso de forma determinística.
Sua função é explicar para o usuário POR QUE este trade faz sentido de acordo com as regras da estratégia.

Contexto recuperado da nossa documentação oficial:
{context}

Sinal gerado pelo motor matemático:
- Tipo: {signal_type}
- Razão matemática: {signal_reason}
- Avaliação de Risco prévia: {risk_evaluation}

Dê uma explicação amigável e curta (máximo 2 parágrafos) justificando este sinal com base na documentação.
Fale como se você estivesse do lado do operador. Destaque alertas de risco se existirem."""

prompt = ChatPromptTemplate.from_messages([
    ("system", system_prompt),
    ("human", "Explique este sinal e os riscos.")
])

agent_chain = prompt | llm | StrOutputParser()

@llm_retry
async def explain_signal(signal: Signal, risk_evaluation: str) -> dict:
    # Desativação temporária da IA explicativa, conforme solicitado.
    return {"analysis": "Análise de IA (RAG) temporariamente desativada."}

if __name__ == "__main__":
    test_signal = Signal(type=SignalType.CALL, reason="9 velas de baixa seguidas")
    print("Testando o Agente...")
    # Ajustado para o novo formato de retorno
    import asyncio
    async def run_test():
        response = await explain_signal(test_signal, "Risco OK. Gale permitido até nível 1.")
        print(response)
    asyncio.run(run_test())
