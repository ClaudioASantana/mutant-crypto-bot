import os
import json
import logging
from typing import List, Dict, Any
from langchain_community.vectorstores import Chroma
from app.rag.vector import get_embeddings

logger = logging.getLogger(__name__)

class ChromaTradeHistory:
    """
    Serviço RAG para indexação e busca de trades históricos.
    Permite à IA tomar decisões baseadas em precedentes de mercado (trades similares passados).
    """
    
    def __init__(self, collection_name: str = "trade_history"):
        self.collection_name = collection_name
        
        base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        db_dir = os.getenv("CHROMA_DB_DIR", "chroma_db")
        self.persist_dir = os.path.join(base_path, db_dir)
        
        try:
            self.vectorstore = Chroma(
                collection_name=self.collection_name,
                persist_directory=self.persist_dir,
                embedding_function=get_embeddings()
            )
            logger.info(f"ChromaTradeHistory inicializado na coleção '{collection_name}'.")
        except Exception as e:
            logger.error(f"Erro ao inicializar ChromaTradeHistory: {e}")
            self.vectorstore = None

    def add_trade(self, trade_data: Dict[str, Any], context_str: str, result_pnl: float):
        """
        Adiciona um trade finalizado ao banco vetorial.
        
        Args:
            trade_data: Metadados do trade (symbol, side, entry_price, etc).
            context_str: Representação textual do contexto de mercado na hora da entrada.
            result_pnl: PnL financeiro ou percentual que define se foi Win ou Loss.
        """
        if not self.vectorstore:
            return

        outcome = "WIN" if result_pnl > 0 else "LOSS" if result_pnl < 0 else "TIE"
        
        # O documento principal é o contexto de mercado
        document = f"Contexto de mercado: {context_str}\nResultado: {outcome} ({result_pnl:.2f})"
        
        # Metadados para filtragem opcional
        metadata = {
            "symbol": trade_data.get("symbol", "UNKNOWN"),
            "side": trade_data.get("side", "UNKNOWN"),
            "outcome": outcome,
            "pnl": float(result_pnl)
        }
        
        # Cria um ID unico basico baseado em epoch/symbol
        doc_id = f"trade_{trade_data.get('entry_time', 0)}_{metadata['symbol']}"
        
        try:
            self.vectorstore.add_texts(
                texts=[document],
                metadatas=[metadata],
                ids=[doc_id]
            )
            logger.debug(f"Trade {doc_id} adicionado ao histórico vetorial com resultado {outcome}.")
        except Exception as e:
            logger.error(f"Erro ao adicionar trade ao ChromaDB: {e}")

    def get_similar_trades(self, current_context_str: str, k: int = 3) -> List[Dict[str, Any]]:
        """
        Busca os k trades mais parecidos com o contexto atual.
        
        Args:
            current_context_str: O texto representando o contexto do mercado atual.
            k: Número de trades similares para recuperar.
            
        Returns:
            Lista de dicionários contendo os metadados e o conteúdo dos trades similares.
        """
        if not self.vectorstore:
            return []
            
        try:
            results = self.vectorstore.similarity_search_with_score(current_context_str, k=k)
            similar_trades = []
            
            for doc, score in results:
                similar_trades.append({
                    "document": doc.page_content,
                    "metadata": doc.metadata,
                    "similarity_score": score
                })
                
            return similar_trades
        except Exception as e:
            logger.error(f"Erro ao buscar trades similares no ChromaDB: {e}")
            return []
