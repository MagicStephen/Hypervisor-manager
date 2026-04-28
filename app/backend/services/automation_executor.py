"""Modul pro spouštění a vyhodnocování automatizačních úloh.

Tento modul zajišťuje vykonávání automatizačních tasků nad virtuálními stroji,
čekání na dokončení vzdálených operací, zpracování stromu navázaných úloh
a ukládání výsledků běhů do databáze.
"""

import asyncio
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.orm import Session

from database.database import SessionLocal
from database.models.automation_task_model import AutomationTask
from database.models.automation_task_run_model import AutomationTaskRun
from database.models.server_model import Server


async def _sleep_after_task(task: AutomationTask):
    """Pozastaví běh po dokončení úlohy podle její konfigurace.

    Pokud má úloha nastavený parametr `duration_seconds` a jeho hodnota je
    větší než nula, funkce na danou dobu uspí běh.

    Args:
        task: Automatizační úloha, ze které se čte doba čekání.
    """
    if task.duration_seconds and task.duration_seconds > 0:
        print(f"[TASK] sleeping {task.duration_seconds}s after task_id={task.id}")
        await asyncio.sleep(task.duration_seconds)


async def _wait_for_task(
    node_api,
    node_id: str,
    task_id: str,
    interval: float = 0.5,
    timeout: int = 300
):
    """Čeká na dokončení vzdálené úlohy na uzlu.

    Funkce periodicky kontroluje stav úlohy přes `node_api` až do jejího
    úspěšného dokončení, selhání nebo vypršení časového limitu.

    Args:
        node_api: API objekt pro práci s uzlem.
        node_id: Identifikátor uzlu.
        task_id: Identifikátor vzdálené úlohy.
        interval: Interval mezi jednotlivými kontrolami stavu v sekundách.
        timeout: Maximální doba čekání v sekundách.

    Returns:
        bool: `True`, pokud úloha skončí úspěšně.

    Raises:
        Exception: Pokud `task_id` chybí.
        Exception: Pokud úloha skončí chybou.
        Exception: Pokud dojde k timeoutu.
    """
    print(f"[WAIT] start node={node_id} task_id={task_id}")

    if not task_id:
        raise Exception("[WAIT] missing task_id")

    start = datetime.now(timezone.utc)

    while True:
        status = node_api.get_task_status(node_id, task_id)

        task_status = str(status.get("status", "")).lower()
        exit_status = str(status.get("exitstatus", "")).lower()

        if task_status == "stopped":
            if exit_status in ("ok", "success", ""):
                return True

            raise Exception(f"Task failed: {exit_status}")

        if (datetime.now(timezone.utc) - start).total_seconds() > timeout:
            raise Exception(f"Task timeout: {task_id}")

        await asyncio.sleep(interval)


async def run_task(app, task_id: int):
    """Spustí automatizační úlohu podle jejího ID.

    Funkce načte úlohu z databáze, ověří, zda je aktivní a zda nejde o
    podřízenou úlohu, a následně spustí celý strom navázaných tasků.
    U jednorázových úloh po úspěšném dokončení deaktivuje další spouštění.

    Args:
        app: Aplikační objekt obsahující sdílený stav aplikace.
        task_id: Identifikátor automatizační úlohy.
    """
    db: Session = SessionLocal()

    try:
        task = db.query(AutomationTask).filter(AutomationTask.id == task_id).first()

        if not task or not task.enabled or task.parent_id is not None:
            return

        if task.trigger_type == "once":
            exists = (
                db.query(AutomationTaskRun)
                .filter(
                    AutomationTaskRun.task_id == task.id,
                    AutomationTaskRun.status == "success"
                )
                .first()
            )
            if exists:
                return

        success = await _run_task_tree(app, db, task)

        if success and task.trigger_type == "once":
            task.enabled = False
            db.commit()

    finally:
        db.close()


async def _run_task_tree(app, db: Session, task: AutomationTask) -> bool:
    """Spustí úlohu a všechny její aktivní podřízené úlohy.

    Funkce nejprve vykoná zadanou úlohu. Pokud uspěje, načte všechny aktivní
    child tasky seřazené podle `order_index` a spustí je rekurzivně.

    Args:
        app: Aplikační objekt obsahující sdílený stav aplikace.
        db: Aktivní databázová session.
        task: Kořenová nebo podřízená automatizační úloha.

    Returns:
        bool: `True`, pokud úspěšně proběhne celá větev úloh, jinak `False`.
    """
    success = await _execute_single_task(app, db, task)
    if not success:
        return False

    children = (
        db.query(AutomationTask)
        .filter(
            AutomationTask.parent_id == task.id,
            AutomationTask.enabled.is_(True)
        )
        .order_by(AutomationTask.order_index.asc(), AutomationTask.id.asc())
        .all()
    )

    for child in children:
        if not await _run_task_tree(app, db, child):
            return False

    return True


async def _execute_single_task(app, db: Session, task: AutomationTask) -> bool:
    """Vykoná jednu konkrétní automatizační úlohu.

    Funkce založí záznam o běhu úlohy, naváže spojení na cílovou platformu
    a podle typu akce provede příslušnou operaci nad virtuálním strojem.
    Po dokončení aktualizuje stav běhu v databázi.

    Podporované akce:
        - `start`
        - `stop`
        - `restart`
        - `snapshot`

    Args:
        app: Aplikační objekt obsahující sdílený stav aplikace.
        db: Aktivní databázová session.
        task: Automatizační úloha, která má být vykonána.

    Returns:
        bool: `True`, pokud úloha proběhne úspěšně, jinak `False`.
    """
    run = None

    try:
        server = task.server

        if not server or not server.auth:
            raise Exception("Server/auth error")

        node_id = task.node_id
        if server.platform.name.lower() == "proxmox" and not node_id:
            raise Exception("Node required")

        run = AutomationTaskRun(
            task_id=task.id,
            status="running",
            started_at=datetime.now(timezone.utc)
        )
        db.add(run)
        db.commit()
        db.refresh(run)

        platform_gw = app.state.platform_gateway

        session_id = platform_gw.connect_automation(server)

        node_api = platform_gw.get_node_api(session_id)
        vm_api = platform_gw.get_vm_api(session_id)

        if task.action == "start":
            result = vm_api.set_vm_status(node_id, task.vm_id, "start")

            await _wait_for_task(node_api, node_id, result.get("task_id"))
            await _sleep_after_task(task)

        elif task.action == "stop":
            result = vm_api.set_vm_status(node_id, task.vm_id, "stop")

            await _wait_for_task(node_api, node_id, result.get("task_id"))
            await _sleep_after_task(task)

        elif task.action == "restart":
            result = vm_api.set_vm_status(node_id, task.vm_id, "reboot")

            await _wait_for_task(node_api, node_id, result.get("task_id"))
            await _sleep_after_task(task)

        elif task.action == "snapshot":
            snapshot_name = f"{task.snapshot_name}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

            result = vm_api.manage_vm_snapshots(
                node_id,
                task.vm_id,
                {
                    "snapname": snapshot_name,
                    "vmstate": 1,
                }
            )

            await _wait_for_task(node_api, node_id, result.get("task_id"), timeout=600)
            await _sleep_after_task(task)

        else:
            raise Exception("Unsupported action")

        run.status = "success"
        run.finished_at = datetime.now(timezone.utc)
        db.commit()

        return True

    except Exception as e:
        if run:
            run.status = "failed"
            run.message = str(e)
            run.finished_at = datetime.now(timezone.utc)
            db.commit()
        else:
            db.rollback()

        return False


async def run_one_time_action(
    app,
    task_id: int,
    serverid: int,
    node_id: str | None,
    vm_id: str,
    action: str,
):
    """Spustí jednorázovou akci nad virtuálním strojem.

    Funkce vytvoří záznam běhu úlohy, připojí se k cílovému serveru
    a provede zadanou akci nad konkrétním VM. Po dokončení uloží výsledek
    do databáze.

    Args:
        app: Aplikační objekt obsahující sdílený stav aplikace.
        task_id: Identifikátor logického tasku, ke kterému se běh přiřadí.
        serverid: Identifikátor cílového serveru.
        node_id: Identifikátor uzlu. Může být `None`, pokud platforma uzel
            nevyžaduje.
        vm_id: Identifikátor virtuálního stroje.
        action: Akce, která má být provedena nad virtuálním strojem.

    Raises:
        Exception: Přeposílá chybu vzniklou během vykonání akce.
    """
    db: Session = SessionLocal()
    run = None

    try:
        server = db.query(Server).filter(Server.id == serverid).first()

        if not server or not server.auth:
            return

        run = AutomationTaskRun(
            task_id=task_id,
            status="running",
            started_at=datetime.now(timezone.utc)
        )
        db.add(run)
        db.commit()
        db.refresh(run)

        platform_gw = app.state.platform_gateway

        session_id = platform_gw.connect_automation(server)

        node_api = platform_gw.get_node_api(session_id)
        vm_api = platform_gw.get_vm_api(session_id)

        result = vm_api.set_vm_status(node_id, vm_id, action)

        await _wait_for_task(node_api, node_id, result.get("task_id"))

        run.status = "success"
        run.finished_at = datetime.now(timezone.utc)
        db.commit()

    except Exception as e:
        if run:
            run.status = "failed"
            run.message = str(e)
            run.finished_at = datetime.now(timezone.utc)
            db.commit()
        else:
            db.rollback()

        raise

    finally:
        db.close()