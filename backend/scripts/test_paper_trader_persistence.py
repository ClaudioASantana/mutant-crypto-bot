#!/usr/bin/env python3
"""
Script de teste para verificar a persistência de estado do PaperTrader
após a refatoração para usar o padrão Repository.
"""

import sys
import os
import json
import tempfile
import shutil

# Adicionar o caminho do backend ao sys.path
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, backend_path)

from app.application.services.simulator import PaperTrader
from app.infrastructure.repositories.json_paper_trader_repository import JsonPaperTraderRepository

def test_persistence():
    # Criar um diretório temporário para os arquivos de estado
    with tempfile.TemporaryDirectory() as temp_dir:
        print(f"📁 Usando diretório temporário: {temp_dir}")

        # Criar o repositório
        repository = JsonPaperTraderRepository(temp_dir)

        # Criar um PaperTrader
        identity = "test_trader_BTCUSDT.json"
        trader = PaperTrader(
            symbol="BTCUSDT",
            identity=identity,
            repository=repository,
            initial_balance=1000.0
        )

        # Verificar estado inicial
        print(f"💰 Saldo inicial: ${trader.balance}")
        assert trader.balance == 1000.0, f"Saldo inicial incorreto: {trader.balance}"

        # Modificar o estado
        trader.balance = 1500.0
        trader.history_trades = [{"id": "test1", "pnl": 100.0}]
        print("🔄 Modificando estado do trader...")

        # Salvar estado
        trader.save_state()
        print("💾 Estado salvo.")

        # Verificar se o arquivo foi criado
        state_file_path = os.path.join(temp_dir, identity)
        assert os.path.exists(state_file_path), f"Arquivo de estado não foi criado: {state_file_path}"
        print(f"✅ Arquivo de estado encontrado: {state_file_path}")

        # Ler o conteúdo do arquivo para verificar
        with open(state_file_path, 'r') as f:
            saved_state = json.load(f)
            print(f"📄 Conteúdo do arquivo de estado: {json.dumps(saved_state, indent=2)}")

        # Criar um novo PaperTrader com o mesmo identity para carregar o estado
        print("🔄 Criando novo PaperTrader para carregar estado...")
        new_trader = PaperTrader(
            symbol="BTCUSDT",
            identity=identity,
            repository=repository,
            initial_balance=1000.0
        )

        # Verificar se o estado foi carregado corretamente
        print(f"💰 Saldo carregado: ${new_trader.balance}")
        assert new_trader.balance == 1500.0, f"Saldo carregado incorreto: {new_trader.balance}"
        assert len(new_trader.history_trades) == 1, f"Histórico de trades incorreto: {len(new_trader.history_trades)}"
        assert new_trader.history_trades[0]["id"] == "test1", f"ID do trade incorreto: {new_trader.history_trades[0]['id']}"

        print("✅ Teste de persistência PASSOU!")
        return True

if __name__ == "__main__":
    try:
        test_persistence()
        print("\n🎉 Todos os testes passaram!")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Teste FALHOU: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)