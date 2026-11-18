from fastapi import FastAPI
from enum import Enum

from app.routes.item import item_router
from app.routes.order import order_router
from app.routes.user import user_router

app = FastAPI()
app.include_router(user_router)
app.include_router(item_router)
app.include_router(order_router)
