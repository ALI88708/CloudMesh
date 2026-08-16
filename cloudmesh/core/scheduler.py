class TaskScheduler:
    def __init__(self, server_manager, resource_monitor):
        self.server_mgr = server_manager
        self.monitor = resource_monitor
        self._tasks = {}

    def get_distribution_plan(self, tasks, server_names=None):
        if server_names is None:
            server_names = self.server_mgr.list_servers()

        all_metrics = {}
        for name in server_names:
            try:
                metrics = self.monitor.get_all_metrics(name)
                weight = self.monitor.calculate_weight(metrics)
                all_metrics[name] = {"metrics": metrics, "weight": weight}
            except Exception:
                all_metrics[name] = {"metrics": None, "weight": 0}

        total_weight = sum(s["weight"] for s in all_metrics.values())
        if total_weight == 0:
            total_weight = len(all_metrics)

        plan = {}
        remaining_tasks = list(range(len(tasks)))

        sorted_servers = sorted(all_metrics.items(), key=lambda x: x[1]["weight"], reverse=True)

        for name, data in sorted_servers:
            if not remaining_tasks:
                break
            weight = data["weight"]
            if weight <= 0:
                continue
            proportion = weight / total_weight
            num_tasks = max(1, round(len(tasks) * proportion))
            assigned = remaining_tasks[:num_tasks]
            remaining_tasks = remaining_tasks[num_tasks:]
            plan[name] = {
                "tasks": [tasks[i] for i in assigned],
                "weight": weight,
                "proportion": round(proportion * 100, 1),
                "metrics": data["metrics"],
            }

        while remaining_tasks:
            for name, _ in sorted_servers:
                if not remaining_tasks:
                    break
                task_idx = remaining_tasks.pop(0)
                if name not in plan:
                    plan[name] = {"tasks": [], "weight": 0, "proportion": 0, "metrics": None}
                plan[name]["tasks"].append(tasks[task_idx])

        return plan

    def run_on_best(self, command):
        best_name, best_weight = self.monitor.get_best_server(self.server_mgr.list_servers())
        if best_name is None:
            return {"success": False, "error": "No servers available"}
        try:
            result = self.server_mgr.execute(best_name, command)
            return {
                "success": result["exit_code"] == 0,
                "server": best_name,
                "weight": best_weight,
                "output": result["stdout"],
                "error": result["stderr"] if result["exit_code"] != 0 else None,
            }
        except Exception as e:
            return {"success": False, "server": best_name, "error": str(e)}

    def distribute_command(self, command, server_names=None):
        if server_names is None:
            server_names = self.server_mgr.list_servers()

        results = {}
        for name in server_names:
            try:
                result = self.server_mgr.execute(name, command)
                results[name] = {
                    "success": result["exit_code"] == 0,
                    "output": result["stdout"],
                    "error": result["stderr"] if result["exit_code"] != 0 else None,
                }
            except Exception as e:
                results[name] = {"success": False, "error": str(e)}
        return results

    def get_status_summary(self):
        servers_metrics = self.monitor.get_all_servers_metrics()
        total_cpu_free = 0
        total_ram_free = 0
        total_disk_free = 0
        connected = 0

        for name, data in servers_metrics.items():
            if data["metrics"] is None:
                continue
            connected += 1
            m = data["metrics"]
            cpu = m.get("cpu_percent")
            if cpu is not None:
                total_cpu_free += 100 - cpu
            ram = m.get("ram") or {}
            total_ram_free += ram.get("free_gb", 0)
            disk = m.get("disk") or {}
            total_disk_free += disk.get("free_gb", 0)

        return {
            "total_servers": len(servers_metrics),
            "connected_servers": connected,
            "total_cpu_free": round(total_cpu_free, 1),
            "total_ram_free_gb": round(total_ram_free, 1),
            "total_disk_free_gb": round(total_disk_free, 1),
            "servers": servers_metrics,
        }

    def slice_files(self, file_list, server_names=None):
        if not file_list:
            return {}
        if server_names is None:
            server_names = self.server_mgr.list_servers()
        if not server_names:
            return {"unassigned": file_list}

        all_metrics = {}
        for name in server_names:
            try:
                metrics = self.monitor.get_all_metrics(name)
                weight = self.monitor.calculate_weight(metrics)
                all_metrics[name] = {"metrics": metrics, "weight": weight}
            except Exception:
                all_metrics[name] = {"metrics": None, "weight": 0}

        total_weight = sum(s["weight"] for s in all_metrics.values())
        if total_weight == 0:
            total_weight = len(all_metrics)

        sorted_servers = sorted(all_metrics.items(), key=lambda x: x[1]["weight"], reverse=True)
        plan = {}
        remaining = list(file_list)

        for name, data in sorted_servers:
            if not remaining:
                break
            weight = data["weight"]
            if weight <= 0:
                continue
            proportion = weight / total_weight
            count = max(1, round(len(file_list) * proportion))
            assigned = remaining[:count]
            remaining = remaining[count:]
            plan[name] = {
                "files": assigned,
                "count": len(assigned),
                "proportion": round(proportion * 100, 1),
                "weight": weight,
            }

        while remaining:
            for name, _ in sorted_servers:
                if not remaining:
                    break
                f = remaining.pop(0)
                if name not in plan:
                    plan[name] = {"files": [], "count": 0, "proportion": 0, "weight": 0}
                plan[name]["files"].append(f)
                plan[name]["count"] += 1

        return plan

    def run_on_best_with_failover(self, command, max_retries=2):
        servers = self.server_mgr.list_servers()
        tried = set()

        for attempt in range(max_retries + 1):
            best_name, best_weight = self.monitor.get_best_server(servers)
            if best_name is None:
                return {"success": False, "error": "No servers available", "attempts": attempt}
            if best_name in tried:
                remaining = [s for s in servers if s not in tried]
                if not remaining:
                    return {"success": False, "error": "All servers tried", "attempts": attempt}
                best_name = remaining[0]
            tried.add(best_name)
            try:
                result = self.server_mgr.execute(best_name, command)
                if result["exit_code"] == 0:
                    return {
                        "success": True,
                        "server": best_name,
                        "output": result["stdout"],
                        "attempts": attempt + 1,
                    }
            except Exception:
                continue

        return {"success": False, "error": "All attempts failed", "attempts": max_retries + 1}
