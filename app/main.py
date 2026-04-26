from fastapi import FastAPI

from app.routers import auth, users, household, menu, subscription, webhook, admin

app = FastAPI(title="Rozkaana", version="1.0.0")

app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(users.router, prefix="/api/v1/users", tags=["users"])
app.include_router(household.router, prefix="/api/v1/household", tags=["household"])
app.include_router(menu.router, prefix="/api/v1/menu", tags=["menu"])
app.include_router(subscription.router, prefix="/api/v1/subscription", tags=["subscription"])
app.include_router(webhook.router, prefix="/api/v1/webhook", tags=["webhook"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["admin"])