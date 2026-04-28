import libvirt
import subprocess
import time
import pprint
import os
import xml.etree.ElementTree as ET

class KvmConnection:
    def __init__(self, host: str):
        self.host = host
        self.username = None
        self.session = None

    def session_connect(self, username: str, password: str | None, mode_type: str = "tcp") -> dict:

        self.username = username

        modes = {
            # "ssh": f"qemu+ssh://{username}@{self.host}/system",
            # "tls": f"qemu+tls://{self.host}/system",
            "tcp": f"qemu+tcp://{self.host}/system",
        }

        uri = modes.get(mode_type)

        if not uri:
            raise ValueError(f"Unsupported connection mode: {mode_type}")

        try:
            if mode_type == "tcp":
                if not password:
                    raise ValueError("Password is required for tcp/SASL mode")

                def request_cred(credentials, user_data):
                    for credential in credentials:
                        cred_type = credential[0]

                        if cred_type == libvirt.VIR_CRED_AUTHNAME:
                            credential[4] = username
                        elif cred_type == libvirt.VIR_CRED_PASSPHRASE:
                            credential[4] = password

                    return 0

                auth = [
                    [libvirt.VIR_CRED_AUTHNAME, libvirt.VIR_CRED_PASSPHRASE],
                    request_cred,
                    None,
                ]

                self.session = libvirt.openAuth(uri, auth, 0)
            else:
                self.session = libvirt.open(uri)

        except libvirt.libvirtError as e:
            msg = str(e).lower()

            if "authentication failed" in msg or "auth" in msg:
                raise PermissionError("Libvirt authentication failed") from e

            if "timeout" in msg or "timed out" in msg:
                raise ConnectionError("Connection to libvirt timed out") from e

            if "connection refused" in msg:
                raise ConnectionError("Connection to libvirt was refused") from e

            raise RuntimeError(f"Libvirt connection error: {e}") from e


    def get_current_metrics(self, ds, host, vm=None):
        
        if not host:
            raise ValueError("Host is needed")

        host_metric_map = {
            "load_avg": "load/load",
            "swap_free": "swap/swap-free",
            "swap_used": "swap/swap-used",
        }

        vm_metric_map = {
            "cpu_usage": "virt_cpu_total",
        }

        requested_metrics = []
        cpu_idle_count = 0

        if vm:
            base_path = f"{host}/virt-{vm}"

            if "cpu_usage" in ds:
                requested_metrics.append(f"{base_path}/{vm_metric_map['cpu_usage']}")

        else:
            # Pro host chceme cpu_usage, load_avg, swap_free, swap_used
            base_path = host

            if "cpu_usage" in ds:

                cpu_num = self.session.getInfo()[2]

                for i in range(cpu_num):
                    requested_metrics.append(f"{host}/cpu-{i}/cpu-idle")
                    cpu_idle_count += 1

            for metric in ds:
                if metric == "cpu_usage":
                    continue

                mapped = host_metric_map.get(metric)
                if mapped:
                    requested_metrics.append(f"{base_path}/{mapped}")

        blocks = []

        if requested_metrics:

            payload = "".join(f'GETVAL "{metric}"\n' for metric in requested_metrics)
            cmd = f"printf '{payload}' | socat - UNIX-CONNECT:/var/run/collectd-unixsock"
            raw = self.run_ssh_command(cmd).strip()

            current = None

            for line in raw.splitlines():
                line = line.strip()
                if not line:
                    continue

                if "Value found" in line or "Values found" in line:
                    current = {}
                    blocks.append(current)
                    continue

                if "=" in line and current is not None:
                    key, value = line.split("=", 1)

                    try:
                        current[key.strip()] = float(value.strip())
                    except ValueError:
                        current[key.strip()] = value.strip()

        result = {}
        idx = 0

        if vm:

            if "cpu_usage" in ds:

                block = blocks[idx]
                value = float(block.get("value", 0.0))

                result["cpu_usage"] = (value / 1e9)

        else:
           
            if cpu_idle_count > 0:
                idle_vals = []

                for _ in range(cpu_idle_count):

                    if idx >= len(blocks):
                        break

                    block = blocks[idx]
                    idx += 1

                    val = block.get("value")

                    if val is not None:
                        idle_vals.append(float(val))

                if idle_vals:

                    avg_idle = sum(idle_vals) / len(idle_vals)
                    cpu_usage = (100.0 - avg_idle) / 100
            
                    result["cpu_usage"] = cpu_usage

            for metric in ds:
                if metric == "cpu_usage":
                    continue
                if metric not in host_metric_map:
                    continue
                if idx >= len(blocks):
                    break

                block = blocks[idx]
                idx += 1

                if metric == "load_avg":
                    result["load_avg"] = [
                        round(float(block.get("shortterm", 0.0)), 2),
                        round(float(block.get("midterm", 0.0)), 2),
                        round(float(block.get("longterm", 0.0)), 2)
                    ]
                elif metric in ("swap_free", "swap_used"):
                    result[metric] = float(block.get("value", 0.0))

            if "swap_free" in result and "swap_used" in result:
                result["swap_total"] = result["swap_free"] + result["swap_used"]

        return result


    def get_rrd_metrics(self, interval: str, cf: str = "AVERAGE", ds: list = None, host=None, vm=None) -> dict:
        
        if not host:
            return {"success": False, "message": "host is required", "data": {}}

        interval_map = {
            "hour": {"fetch": "-1h", "resolution": 60},
            "day": {"fetch": "-1d", "resolution": 300},
            "week": {"fetch": "-7d", "resolution": 1800},
        }

        if interval not in interval_map:
            return {"success": False, "message": f"Unsupported interval: {interval}", "data": {}}

        fetch_config = interval_map[interval]
        base_path = f"/var/lib/collectd/rrd/{host}"

        def _fetch_rrd(file_path: str) -> str:
            cmd = f"rrdtool fetch {file_path} {cf} -s {fetch_config['fetch']} -e now -r {fetch_config['resolution']}"
            return self.run_ssh_command(cmd)

        def _parse_rrd_rows(output: str) -> list[dict]:
            lines = [line.strip() for line in output.splitlines() if line.strip()]
            if not lines:
                return []

            header = lines[0].split()
            rows = []

            for line in lines[1:]:
                if ":" not in line:
                    continue

                ts_part, values_part = line.split(":", 1)
                values = values_part.split()

                if len(values) != len(header):
                    continue

                if any(v.lower() == "nan" for v in values):
                    continue

                try:
                    rows.append({
                        "timestamp": ts_part.strip(),
                        "values": {header[i]: float(values[i]) for i in range(len(header))}
                    })
                except ValueError:
                    continue

            return rows

        def _add_single_series(file_path: str, metric_name: str, data: dict):
            raw = _fetch_rrd(file_path)
            rows = _parse_rrd_rows(raw)

            for row in rows:
                ts = row["timestamp"]
                val = next(iter(row["values"].values()))

                if ts not in data:
                    data[ts] = {}
                    

                data[ts][metric_name] = val

        def _add_multi_series(file_paths: list[str], ds_to_metric: dict, data: dict):
            for file_path in file_paths:
                raw = _fetch_rrd(file_path)
                rows = _parse_rrd_rows(raw)

                for row in rows:
                    ts = row["timestamp"]

                    if ts not in data:
                        data[ts] = {}

                    for ds_name, metric_name in ds_to_metric.items():
                        if ds_name in row["values"]:
                            data[ts][metric_name] = data[ts].get(metric_name, 0.0) + row["values"][ds_name]

        def _remote_find(expr: str) -> list[str]:
            cmd = f"find {base_path} -type f {expr}"
            out = self.run_ssh_command(cmd)
            return [line.strip() for line in out.splitlines() if line.strip()]

        data = {}

        if vm:
            vm_path = f"{base_path}/virt-{vm}"

            # single files
            _add_single_series(f"{vm_path}/virt_cpu_total.rrd", "cpu_usage", data)
            _add_single_series(f"{vm_path}/memory-total.rrd", "memory_total", data)
            _add_single_series(f"{vm_path}/memory-unused.rrd", "memory_free", data)

            # multi files
            vm_net_files = _remote_find(f"-path '{vm_path}/if_octets-*.rrd'")
            vm_disk_files = _remote_find(f"-path '{vm_path}/disk_octets-*.rrd'")

            _add_multi_series(vm_net_files, {"rx": "net_in", "tx": "net_out"}, data)
            _add_multi_series(vm_disk_files, {"read": "disk_read", "write": "disk_write"}, data)

        else:
            # host metrics
            _add_single_series(f"{base_path}/memory/memory-used.rrd", "memory_used", data)
            _add_single_series(f"{base_path}/memory/memory-free.rrd", "memory_free", data)
            _add_single_series(f"{base_path}/load/load.rrd", "load_avg", data)

            # CPU host -> z idle spočítat usage
            cpu_idle_files = _remote_find(f"-path '{base_path}/cpu-*/cpu-idle.rrd'")
            _add_multi_series(cpu_idle_files, {"value": "cpu_idle_sum"}, data)

            # NET host
            host_net_files = _remote_find(f"-path '{base_path}/interface-*/if_octets.rrd'")
            _add_multi_series(host_net_files, {"rx": "net_in", "tx": "net_out"}, data)

            # DISK host
            host_disk_files = _remote_find(f"-path '{base_path}/disk-*/disk_octets.rrd'")
            _add_multi_series(host_disk_files, {"read": "disk_read", "write": "disk_write"}, data)

            # host memory_total = used + free
            for ts, metrics in data.items():
                if "memory_used" in metrics and "memory_free" in metrics:
                    metrics["memory_total"] = metrics["memory_used"] + metrics["memory_free"]

            # host cpu_usage = 100 - average idle
            cpu_count = len(cpu_idle_files)
            if cpu_count > 0:
                for ts, metrics in data.items():
                    if "cpu_idle_sum" in metrics:
                        avg_idle = metrics["cpu_idle_sum"] / cpu_count
                        metrics["cpu_usage"] = round(max(0.0, min(100.0, 100.0 - avg_idle)), 2)
                        del metrics["cpu_idle_sum"]

        # vm memory_used
        if vm:
         
            for ts, metrics in data.items():

                if "cpu_usage" in metrics and metrics["cpu_usage"] is not None:
                    metrics["cpu_usage"] = (metrics["cpu_usage"] / 1e9)

                if "memory_total" in metrics and "memory_free" in metrics:
                    metrics["memory_used"] = metrics["memory_total"] - metrics["memory_free"]

        sorted_data = dict(sorted(data.items(), key=lambda x: int(x[0])))

        return {
            "success": True,
            "message": "Metrics fetch successful",
            "data": sorted_data
        }
    
    def run_ssh_command(self, command: str) -> str:
        result = subprocess.run(
            ["ssh", f"{self.username}@{self.host}", command],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
        return result.stdout
    
    def copy_file_to_remote(self, local_path: str, remote_path: str):
        subprocess.run(
            [
                "scp",
                local_path,
                f"{self.username}@{self.host}:{remote_path}",
            ],
            check=True,
        )

    def disconnect(self):
        if self.session:
            self.session.close()
            self.session = None