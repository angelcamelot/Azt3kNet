# 🜂 Azt3kNet

**Cyber-Aztec network for social media bot research and creative automation (Simulation Mode)**  

---

## 🧠 Overview
**Azt3kNet** is an **educational and experimental project** that simulates a network of digital personas — autonomous agents with names, countries, interests, and behaviors — to explore how AI can model social interaction, content generation, and influence flow in a **controlled sandbox environment**.

This is **not** a platform for real bot deployment or account farming.  
Instead, Azt3kNet acts as a **research ecosystem** where developers can:
- Create and study AI-driven personas.  
- Generate posts and interactions using local LLMs.  
- Observe algorithmic and behavioral patterns safely and ethically.  

---

## ⚙️ Core Idea — DeepSeek in Local Mode
The project integrates **DeepSeek (local)** as the main text-generation engine for creating captions, bios, and simulated conversations.  
Running DeepSeek locally offers:
- 🧩 **Privacy** — your data never leaves your machine.  
- ⚡ **Low latency** — no cloud dependency.  
- 🧱 **Full control** — works even on older Intel Macs via quantized models (1.3B / 2B).  

DeepSeek can be accessed through:
- **Ollama** → `ollama serve` + `ollama pull deepseek-coder:1.3b`  
- **Llama.cpp** or **LM Studio** → for other hardware setups.

---

## 🔧 Architecture Snapshot
- **Persona Generator** → creates N agents with unique traits.  
- **Content Engine** → generates drafts per agent using DeepSeek local.  
- **Simulator** → emulates follows, likes, and comments in a closed network.  
- **Scheduler** → queues posts with human approval before any real action.  
- **Inbox Module (optional)** → reads IMAP messages from your own domain; can open links via sandboxed Playwright.  
- **Integrations Layer** → optional, compliant connectors to official APIs (e.g., Meta Graph API), disabled by default.  

---

## 🧱 Tech Stack
- **Python 3.11**  
- **FastAPI** for orchestration  
- **SQLModel / SQLite** for storage  
- **Playwright** (headless browser sandbox)  
- **DeepSeek (local)** via Ollama or llama.cpp  
- **Dotenv + Structured Logging** for configuration and auditing  

---

## 🚀 Quickstart (Simulation Mode)

```bash
git clone https://github.com/youruser/azt3knet.git
cd azt3knet
cp .env.example .env     # fill your local config
bash scripts/setup.sh    # installs Python deps + Playwright
ollama serve             # optional, if using DeepSeek local
ollama pull deepseek-coder:1.3b
bash scripts/run_local.sh
