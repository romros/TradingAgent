from fastapi import FastAPI
from apps.agent.routes import router

app = FastAPI(title="TradingAgent Paper Probe", version="0.1.0")
app.include_router(router)
