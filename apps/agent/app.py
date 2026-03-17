import logging
from fastapi import FastAPI
from apps.agent.routes import router

# Logs estructurats del paper probe (scan, settlement)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

app = FastAPI(title="TradingAgent Paper Probe", version="0.1.0")
app.include_router(router)
