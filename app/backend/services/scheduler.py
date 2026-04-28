"""Modul pro plánování a registraci automatizačních úloh.

Tento modul obsahuje obsluhu plánovače založeného na APScheduleru.
Zajišťuje načítání automatizačních tasků z databáze, jejich registraci
do scheduleru, mazání již neplatných úloh a spouštění wrapperu, který
vykoná samotný task.
"""

from datetime import datetime, timezone

from apscheduler.jobstores.base import JobLookupError
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger
from sqlalchemy.orm import Session

from database.database import SessionLocal
from database.models.automation_task_model import AutomationTask
from database.models.automation_task_run_model import AutomationTaskRun


class Scheduler:
    """Třída pro správu plánovače automatizačních úloh.

    Třída obaluje `AsyncIOScheduler` a poskytuje metody pro:
    
    - spuštění a zastavení scheduleru,
    - registraci úloh podle databázové konfigurace,
    - opětovné načtení tasků,
    - odstranění úloh,
    - sestavení triggerů podle typu plánování.
    """

    def __init__(self):
        """Inicializuje plánovač pro časové pásmo Europe/Prague."""
        self.scheduler = AsyncIOScheduler(timezone="Europe/Prague")

    def start(self, app=None):
        """Spustí scheduler a volitelně načte tasky z databáze.

        Pokud scheduler ještě neběží, metoda jej spustí. Pokud je předán
        aplikační objekt, následně do scheduleru načte dostupné tasky.

        Args:
            app: Volitelný aplikační objekt obsahující sdílený stav aplikace.
        """
        if not self.scheduler.running:
            self.scheduler.start()
            print("[SCHEDULER] started")

        if app is not None:
            self.load_tasks(app)

    def stop(self):
        """Zastaví scheduler bez čekání na dokončení běžících úloh."""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            print("[SCHEDULER] stopped")

    def every(self, seconds: int, func, *args, **kwargs):
        """Zaregistruje intervalovou úlohu spouštěnou každých N sekund.

        Args:
            seconds: Interval spouštění v sekundách.
            func: Funkce, která má být vykonávána.
            *args: Poziční argumenty předané funkci.
            **kwargs: Pojmenované argumenty předané funkci.

        Returns:
            Job: Objekt zaregistrované scheduler úlohy.
        """
        job = self.scheduler.add_job(
            func=func,
            trigger=IntervalTrigger(seconds=seconds, timezone="Europe/Prague"),
            args=args,
            kwargs=kwargs,
        )
        print(f"[SCHEDULER] interval job added id={job.id}")
        return job

    def load_tasks(self, app):
        """Načte root aktivní tasky z databáze a zaregistruje je.

        Před načtením smaže všechny již existující automation joby,
        aby nedocházelo k duplicitám. Jednorázové tasky, které již byly
        úspěšně vykonány, se znovu neregistrují.

        Args:
            app: Aplikační objekt obsahující sdílený stav aplikace.
        """
        self._clear_automation_jobs()

        db: Session = SessionLocal()
        try:
            tasks = (
                db.query(AutomationTask)
                .filter(
                    AutomationTask.enabled.is_(True),
                    AutomationTask.parent_id.is_(None),
                )
                .all()
            )

            print(f"[SCHEDULER] loading {len(tasks)} root tasks")

            for task in tasks:
                if task.trigger_type == "once":
                    already_executed = (
                        db.query(AutomationTaskRun)
                        .filter(
                            AutomationTaskRun.task_id == task.id,
                            AutomationTaskRun.status == "success",
                        )
                        .first()
                    )

                    if already_executed:
                        print(f"[SCHEDULER] skipping once task {task.id}, already executed")
                        continue

                self.register_task(app, task)

            self.print_jobs()

        finally:
            db.close()

    def reload_tasks(self, app):
        """Znovu načte tasky z databáze a zaregistruje je do scheduleru.

        Args:
            app: Aplikační objekt obsahující sdílený stav aplikace.
        """
        self.load_tasks(app)

    def remove_task(self, task_id: int):
        """Odstraní naplánovanou úlohu podle ID tasku.

        Args:
            task_id: Identifikátor automatizační úlohy.
        """
        job_id = f"automation_task_{task_id}"
        try:
            self.scheduler.remove_job(job_id)
            print(f"[SCHEDULER] removed job {job_id}")
        except JobLookupError:
            pass

    def register_task(self, app, task: AutomationTask):
        """Zaregistruje root task do scheduleru.

        Registrují se pouze aktivní root tasky. Child tasky nejsou
        plánovány samostatně, protože se spouštějí v rámci stromu úloh.

        Args:
            app: Aplikační objekt obsahující sdílený stav aplikace.
            task: Automatizační úloha, která má být zaregistrována.

        Returns:
            Job | None: Zaregistrovaná scheduler úloha, nebo `None`,
            pokud task nelze registrovat.
        """
        if task.parent_id is not None:
            print(f"[SCHEDULER] task {task.id} is child, not registering directly")
            return None

        if not task.enabled:
            print(f"[SCHEDULER] task {task.id} is disabled, not registering")
            return None

        job_id = f"automation_task_{task.id}"
        self.remove_task(task.id)

        trigger = self._build_trigger(task)
        if not trigger:
            print(f"[SCHEDULER] task {task.id} has invalid trigger")
            return None

        job = self.scheduler.add_job(
            func=run_task_wrapper,
            trigger=trigger,
            args=[app, task.id],
            id=job_id,
            replace_existing=True,
            coalesce=True,
            max_instances=1,
            misfire_grace_time=60,
        )

        print(
            f"[SCHEDULER] registered task id={task.id}, "
            f"job_id={job_id}, trigger={task.trigger_type}, next_run={job.next_run_time}"
        )
        return job

    def _build_trigger(self, task: AutomationTask):
        """Vytvoří scheduler trigger podle konfigurace tasku.

        Podporované typy triggerů:
        - `interval`
        - `once`
        - `cron`

        Args:
            task: Automatizační úloha obsahující plánovací parametry.

        Returns:
            BaseTrigger | None: Vytvořený APScheduler trigger,
            nebo `None`, pokud konfigurace není validní.
        """
        if task.trigger_type == "interval" and task.interval_seconds:
            return IntervalTrigger(
                seconds=task.interval_seconds,
                timezone="Europe/Prague",
            )

        if task.trigger_type == "once" and task.run_at:
            run_at = task.run_at

            if run_at.tzinfo is None:
                run_at = run_at.replace(tzinfo=timezone.utc)

            now = datetime.now(timezone.utc)

            if run_at < now:
                print(f"[SCHEDULER] once task {task.id} has past run_at, scheduling immediately")
                return DateTrigger(run_date=now, timezone="UTC")

            return DateTrigger(run_date=run_at)

        if task.trigger_type == "cron" and task.cron_expression:
            try:
                return CronTrigger.from_crontab(
                    task.cron_expression,
                    timezone="Europe/Prague",
                )
            except Exception as e:
                print(f"[SCHEDULER] invalid cron for task {task.id}: {task.cron_expression} | {e}")
                return None

        return None

    def _clear_automation_jobs(self):
        """Odstraní všechny automation joby aktuálně registrované ve scheduleru."""
        jobs = self.scheduler.get_jobs()
        for job in jobs:
            if job.id.startswith("automation_task_"):
                try:
                    self.scheduler.remove_job(job.id)
                except JobLookupError:
                    pass

    def print_jobs(self):
        """Vypíše seznam aktuálně registrovaných scheduler úloh."""
        jobs = self.scheduler.get_jobs()
        print("[SCHEDULER] active jobs:")
        for job in jobs:
            print(f"  - id={job.id}, next_run={job.next_run_time}, trigger={job.trigger}")


async def run_task_wrapper(app, task_id: int):
    """Wrapper pro spuštění automatizační úlohy přes scheduler.

    Funkce je registrována ve scheduleru jako cílová akce a dynamicky
    importuje vykonávací logiku tasku, aby se předešlo cyklickým importům.

    Args:
        app: Aplikační objekt obsahující sdílený stav aplikace.
        task_id: Identifikátor automatizační úlohy.
    """
    print(f"[SCHEDULER] triggering task {task_id}")
    from services.automation_executor import run_task
    await run_task(app, task_id)