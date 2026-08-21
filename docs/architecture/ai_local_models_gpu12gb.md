# Arquitetura de IA Local (12GB VRAM + llama-cpp-turboquant)

Este documento registra a decisão e a configuração recomendada para a execução local da camada de Inteligência Artificial do `mutant-crypto-bot`, utilizando o motor **llama-cpp-turboquant** em um servidor Ubuntu com GPU NVIDIA de 12GB de VRAM.

## Contexto
Anteriormente dependíamos da OpenAI (GPT-4o-mini) via API. Com o objetivo de rodar modelos locais mais robustos e seguros (zero-knowledge para a nuvem externa) sem abrir mão de raciocínio lógico avançado para trading, migramos a infraestrutura para usar o `llama-server` incluído no fork do TurboQuant+.

O servidor possui **12GB de VRAM**. Para obter um desempenho equiparável ou superior ao GPT-4o-mini em tarefas analíticas de trading e código, recomendamos as seguintes opções de modelos.

---

## 1. Qwen2.5-14B-Instruct (Recomendação Principal)
O modelo ideal que cabe perfeitamente na capacidade do hardware atual. A família Qwen2.5 superou consistentemente o GPT-4o-mini e o Llama 3.1 8B em benchmarks de raciocínio, lógica e código (tarefas essenciais para atuar como "Veto Layer" no trading).

- **Tamanho na GPU:** Utilizando a quantização `TQ4_1S` do TurboQuant+ (ou alternativamente `Q4_K_M`), o modelo ocupa cerca de **8 GB a 9 GB** de VRAM.
- **Folga de Contexto:** Deixa entre **3 GB a 4 GB livres** para o Cache KV (o contexto da conversa). Isso é ideal e totalmente suficiente para injetarmos o histórico de trades passados via RAG antes de pedir a decisão da IA.
- **Uso de Caso:** Muito analítico, lida perfeitamente com raciocínio estruturado, matemática financeira e saídas restritas em formato JSON.

## 2. Llama-3.1-8B-Instruct (A Alternativa Super Rápida)
Caso haja necessidade de processar um volume gigantesco de contexto simultâneo ou requisições paralelas, o Llama-3.1 8B é o padrão ouro na sua faixa de peso, oferecendo extrema confiabilidade com formatação de respostas JSON.

- **Tamanho na GPU:** Com quantização em ~4.5 bits (`TQ4_1S`), ocupa apenas cerca de **5 GB** de VRAM.
- **Folga de Contexto:** Deixa impressionantes **7 GB livres**. Com isso, é possível operar um tamanho de contexto brutalmente longo sem se preocupar minimamente com "Out of Memory" (OOM).

---

## Como integrar com o Bot?
A beleza de usar o `llama-cpp-turboquant` é que o seu binário servidor (`llama-server`) disponibiliza nativamente uma API **100% compatível** com o padrão da OpenAI. 

Não é necessário reescrever a biblioteca Python `openai` no código do bot. A integração exige apenas a alteração das credenciais no arquivo `.env`:

```env
OPENAI_API_KEY="sk-no-key-required"
OPENAI_BASE_URL="http://ip-do-servidor-ubuntu:8080/v1"
```

A camada `ia_filter_interface.py` do bot irá disparar os mesmos payloads de *Few-Shot Prompting* que já utilizávamos, mas agora direcionados para o motor quantizado localmente.
