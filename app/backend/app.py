from dotenv import load_dotenv
load_dotenv()

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import user_router, node_router, server_router, vm_router, automation_router

from sessions.session_manager import SessionManager
from platforms.platform_gateway import PlatformGateway
from config import CORS_ORIGINS
from services.scheduler import Scheduler
from database.database import Base, engine

from database.models.platform_model import Platform
from database.models.user_model import User
from database.models.server_model import Server
from database.models.node_model import Node
from database.models.server_node_model import ServerNode
from database.models.server_automation_auth_model import ServerAutomationAuth
from database.models.automation_task_model import AutomationTask
from database.models.automation_task_run_model import AutomationTaskRun


session_manager = SessionManager()
platform_gateway = PlatformGateway(session_manager)
scheduler = Scheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)

    app.state.session_manager = session_manager
    app.state.platform_gateway = platform_gateway
    app.state.scheduler = scheduler

    scheduler.every(30, session_manager.cleanup)
    scheduler.start(app)

    try:
        yield
    finally:
        scheduler.stop()


app = FastAPI(lifespan=lifespan)

app.include_router(vm_router.router, prefix="/servers/{serverid}/vms", tags=["Virtual Machines"])
app.include_router(node_router.router, prefix="/servers/{serverid}/nodes", tags=["Nodes"])
app.include_router(automation_router.router, prefix="/servers/{serverid}/tasks", tags=["Automation Tasks"])

app.include_router(server_router.router, prefix="/servers", tags=["Servers"])
app.include_router(user_router.router, prefix="/users", tags=["Users"])

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)