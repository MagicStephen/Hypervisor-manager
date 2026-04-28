"""Router pro správu automatizací.

Obsahuje endpointy pro:

- správu autentizačních údajů pro automatizaci
- správu automatizačních úloh (tasks)
- vytváření, načítání a mazání úloh

Všechny endpointy vyžadují validní autentizační token uložený v cookie
`user_token`.
"""

from fastapi import APIRouter, Depends, Cookie, Request
from sqlalchemy.orm import Session

from database.database import get_db
from services.user_service import UserService
from services.automation_service import AutomationService
from database.models.automation_task_model import AutomationTask

router = APIRouter()


@router.post("/automation-auth", response_model=dict)
def set_automation_auth(
    serverid: int,
    data: dict,
    user_token: str = Cookie(None),
    db: Session = Depends(get_db)
):
    """Uloží autentizační údaje pro automatizaci k danému serveru.

    Args:
        serverid (int): Identifikátor serveru.
        data (dict): Přihlašovací údaje nebo konfigurační data pro automatizaci.
        user_token (str | None): Autentizační token uložený v cookie.
        db (Session): Aktivní databázová session.

    Returns:
        dict: Výsledek operace uložení autentizačních údajů.

    Raises:
        HTTPException: Pokud je token neplatný nebo operace selže.
    """
    user_id = UserService().validate_token(user_token, db, True)
    return AutomationService.set_automation_auth(
        server_id=serverid,
        credentials=data,
        user_id=user_id,
        db=db
    )


@router.get("/automation-auth", response_model=dict)
def get_automation_auth(
    serverid: int,
    user_token: str = Cookie(None),
    db: Session = Depends(get_db)
):
    """Vrátí uložené autentizační údaje pro automatizaci.

    Args:
        serverid (int): Identifikátor serveru.
        user_token (str | None): Autentizační token uložený v cookie.
        db (Session): Aktivní databázová session.

    Returns:
        dict: Uložené autentizační údaje nebo prázdný objekt, pokud neexistují.

    Raises:
        HTTPException: Pokud je token neplatný nebo data nelze načíst.
    """
    user_id = UserService().validate_token(user_token, db, True)
    return AutomationService.get_automation_auth(
        server_id=serverid,
        user_id=user_id,
        db=db
    )


@router.delete("/automation-auth/{auth_id}", response_model=dict)
def delete_automation_auth(
    serverid: int,
    auth_id: int,
    user_token: str = Cookie(None),
    db: Session = Depends(get_db)
):
    """Smaže autentizační údaje pro automatizaci.

    Args:
        serverid (int): Identifikátor serveru.
        auth_id (int): Identifikátor autentizačního záznamu.
        user_token (str | None): Autentizační token uložený v cookie.
        db (Session): Aktivní databázová session.

    Returns:
        dict: Výsledek operace smazání.

    Raises:
        HTTPException: Pokud je token neplatný nebo mazání selže.
    """
    user_id = UserService().validate_token(user_token, db, True)
    return AutomationService.delete_automation_auth(
        server_id=serverid,
        auth_id=auth_id,
        user_id=user_id,
        db=db
    )


@router.get("/automation-tasks", response_model=list[dict])
def get_automation_tasks(
    serverid: int,
    user_token: str = Cookie(None),
    db: Session = Depends(get_db)
):
    """Vrátí seznam automatizačních úloh pro daný server.

    Args:
        serverid (int): Identifikátor serveru.
        user_token (str | None): Autentizační token uložený v cookie.
        db (Session): Aktivní databázová session.

    Returns:
        list[dict]: Seznam automatizačních úloh. Každá položka obsahuje
        metadata úlohy (např. ID, název, stav, plánování apod.).

    Raises:
        HTTPException: Pokud je token neplatný nebo data nelze načíst.
    """
    user_id = UserService().validate_token(user_token, db, True)
    
    rest = AutomationService.get_automation_tasks(
        server_id=serverid,
        user_id=user_id,
        db=db
    )

    print(rest)

    return rest


@router.post("/automation-task", response_model=dict)
def create_task(
    serverid: int,
    data: dict,
    request: Request,
    user_token: str = Cookie(None),
    db: Session = Depends(get_db)
):
    """Vytvoří novou automatizační úlohu.

    Pokud se jedná o hlavní úlohu (bez parent_id), je automaticky
    zaregistrována do scheduleru aplikace.

    Args:
        serverid (int): Identifikátor serveru.
        data (dict): Konfigurace automatizační úlohy.
        request (Request): FastAPI request pro přístup ke scheduleru aplikace.
        user_token (str | None): Autentizační token uložený v cookie.
        db (Session): Aktivní databázová session.

    Returns:
        dict: Vytvořená automatizační úloha včetně ID a konfigurace.

    Raises:
        HTTPException: Pokud je token neplatný nebo vytvoření úlohy selže.
    """
    user_id = UserService().validate_token(user_token, db, True)

    task = AutomationService.create_automation_task(
        server_id=serverid,
        user_id=user_id,
        data=data,
        db=db
    )

    if task["parent_id"] is None:
        db_task = db.query(AutomationTask).filter(AutomationTask.id == task["id"]).first()
        if db_task:
            request.app.state.scheduler.register_task(request.app, db_task)

    return task


@router.delete("/automation-task/{taskid}", response_model=dict)
def delete_automation_task(
    serverid: int,
    taskid: int,
    request: Request,
    user_token: str = Cookie(None),
    db: Session = Depends(get_db)
):
    """Smaže automatizační úlohu.

    Pokud se jedná o hlavní úlohu (bez parent_id), je zároveň odstraněna
    ze scheduleru aplikace.

    Args:
        serverid (int): Identifikátor serveru.
        taskid (int): Identifikátor úlohy.
        request (Request): FastAPI request pro přístup ke scheduleru aplikace.
        user_token (str | None): Autentizační token uložený v cookie.
        db (Session): Aktivní databázová session.

    Returns:
        dict: Výsledek operace smazání úlohy.

    Raises:
        HTTPException: Pokud je token neplatný nebo mazání selže.
    """
    user_id = UserService().validate_token(user_token, db, True)

    task = AutomationService.delete_automation_task(
        server_id=serverid,
        task_id=taskid,
        user_id=user_id,
        db=db
    )

    if task["parent_id"] is None:
        try:
            request.app.state.scheduler.remove_task(task["id"])
        except Exception as e:
            print(f"Failed to remove task {task['id']} from scheduler: {e}")

    return task