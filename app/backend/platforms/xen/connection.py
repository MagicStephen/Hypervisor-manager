import uuid
import requests
import time
import os 
from urllib.parse import urlencode
from fastapi import HTTPException

class XenConnection:
    def __init__(self, host: str):
        self.host = host
        self.session = None

        self.url = f"https://{self.host}/jsonrpc"
        
        self.headers = {
            "Content-Type": "application/json"
        }

        self.TIMEFRAME_TO_SECONDS = {
            "current": 10,
            "hour": 3600,
            "day": 86400,
            "week": 604800,
            "month": 2592000,   
            "year": 31536000,
            "decade": 315360000
        }

    def session_connect(self, username: str, password: str):

        self.session = self.request(
            "POST",
            "session.login_with_password",
            [username, password]
        )

    def import_xva(self, file_path: str, session_ref: str, host_ref: str | None = None):
        if not os.path.exists(file_path):
            raise ValueError(f"File '{file_path}' does not exist")

        sr_ref = None

        if not sr_ref:
            sr_records = self.request(
                "POST",
                "SR.get_all_records",
                [session_ref]
            ) or {}

            local_sr_ref = None

            for ref, sr in sr_records.items():
                if not sr:
                    continue

                name = (sr.get("name_label") or "").lower()
                content_type = sr.get("content_type")
                sr_type = sr.get("type")

                if "local" not in name:
                    continue

                if content_type != "user":
                    continue

                if sr_type == "udev":
                    continue

                local_sr_ref = ref
                break

            if not local_sr_ref:
                raise ValueError("Local storage was not found")

            sr_ref = local_sr_ref

        vms_before = self.request(
            "POST",
            "VM.get_all_records",
            [session_ref]
        ) or {}

        before_uuids = {
            rec.get("uuid"): ref
            for ref, rec in vms_before.items()
            if rec and not rec.get("is_a_template") and not rec.get("is_control_domain")
        }

        task_ref = self.request(
            "POST",
            "task.create",
            [
                session_ref,
                f"Import {os.path.basename(file_path)}",
                f"Import XVA from {file_path}",
            ]
        )

        params = {
            "session_id": session_ref,
            "task_id": task_ref,
            "sr_id": sr_ref,
        }

        if host_ref:
            params["host_id"] = host_ref

        url = f"https://{self.host}/import?{urlencode(params)}"

        with open(file_path, "rb") as fh:
            response = requests.put(
                url,
                data=fh,
                headers={
                    "Content-Type": "application/octet-stream",
                    "Content-Length": str(os.path.getsize(file_path)),
                },
                verify=False,
                timeout=3600,
            )

        response.raise_for_status()

        task_status = None
        for _ in range(120):
            task_status = self.request(
                "POST",
                "task.get_record",
                [session_ref, task_ref]
            )

            status = (task_status or {}).get("status")
            if status in ("success", "failure", "cancelled"):
                break

            time.sleep(5)

        task_result = self.request(
            "POST",
            "task.get_result",
            [session_ref, task_ref]
        )

        vm_ref = None

        if isinstance(task_result, str) and task_result.startswith("OpaqueRef:"):
            vm_ref = task_result
        elif isinstance(task_result, dict):
            vm_ref = task_result.get("Value") or task_result.get("value")

        if not vm_ref:
            vms_after = self.request(
                "POST",
                "VM.get_all_records",
                [session_ref]
            ) or {}

            for ref, rec in vms_after.items():
                if not rec or rec.get("is_a_template") or rec.get("is_control_domain"):
                    continue

                vm_uuid = rec.get("uuid")
                if vm_uuid and vm_uuid not in before_uuids:
                    vm_ref = ref
                    break

        return {
            "task_ref": task_ref,
            "task_status": task_status,
            "task_result": task_result,
            "vm_ref": vm_ref,
            "sr_ref": sr_ref,
        }

    def request(self, http_method: str, xen_method: str, params: list | None = None, timeout=30):
        if params is None:
            params = []

        payload = {
            "id": str(uuid.uuid4()),
            "jsonrpc": "2.0",
            "method": xen_method,
            "params": params,
        }

        try:
            response = requests.request(
                method=http_method,
                url=self.url,
                json=payload,
                headers=self.headers,
                verify=False,
                timeout=timeout
            )

            response.raise_for_status()

        except requests.exceptions.RequestException as e:
            print("REQUEST ERROR:", repr(e))

            if getattr(e, "response", None) is not None:
                print("STATUS:", e.response.status_code)
                print("BODY:", e.response.text)

            raise HTTPException(
                status_code=503,
                detail=f"Connection to Xen API failed: {repr(e)}"
            ) from e

        try:
            resp_json = response.json()
        except ValueError as e:
            raise HTTPException(
                status_code=500,
                detail=f"Invalid JSON response from Xen API: {response.text}"
            ) from e

        if "error" in resp_json:
            raise HTTPException(
                status_code=400,
                detail=resp_json["error"]
            )

        return resp_json.get("result")
    
    def get_xapi_obj_ref(self, object: str, id: str):

        vm_ref = self.request(
            "POST",
            f"{object}.get_by_uuid",
            [self.session, id]
        )

        return vm_ref
    
    def get_xapi_obj_record(self, object: str, object_ref: str):

        return self.request(
            "POST",
            f"{object}.get_record",
            [self.session, object_ref]
        )