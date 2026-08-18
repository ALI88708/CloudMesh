import json
import time
from pathlib import Path
from datetime import datetime


ALPHA = 0.3


class WeatherForecast:
    def __init__(self, data_file=None):
        self.data_file = Path(data_file or Path(__file__).parent.parent / ".resource_weather.json")
        self._data = self._load()

    def _load(self):
        if self.data_file.exists():
            try:
                return json.loads(self.data_file.read_text())
            except Exception:
                pass
        return {}

    def _save(self):
        self.data_file.write_text(json.dumps(self._data, indent=2))

    def learn(self, server_name, cpu_percent, ram_percent):
        now = datetime.now()
        hour = now.hour

        if server_name not in self._data:
            self._data[server_name] = {}

        if hour not in self._data[server_name]:
            self._data[server_name][hour] = {
                "cpu_ema": cpu_percent,
                "ram_ema": ram_percent,
                "samples": 1,
            }
        else:
            slot = self._data[server_name][hour]
            slot["cpu_ema"] = round(ALPHA * cpu_percent + (1 - ALPHA) * slot["cpu_ema"], 2)
            slot["ram_ema"] = round(ALPHA * ram_percent + (1 - ALPHA) * slot["ram_ema"], 2)
            slot["samples"] += 1

        self._save()

    def learn_from_metrics(self, server_name, metrics):
        if not metrics:
            return
        cpu = metrics.get("cpu_percent", 0) or 0
        ram = (metrics.get("ram") or {}).get("percent", 0) or 0
        self.learn(server_name, cpu, ram)

    def predict(self, server_name, target_hour=None):
        if target_hour is None:
            target_hour = (datetime.now().hour + 1) % 24

        server_data = self._data.get(server_name, {})
        slot = server_data.get(target_hour)

        if not slot:
            return {
                "hour": target_hour,
                "cpu_ema": None,
                "ram_ema": None,
                "samples": 0,
                "status": "no_data",
            }

        return {
            "hour": target_hour,
            "cpu_ema": slot["cpu_ema"],
            "ram_ema": slot["ram_ema"],
            "samples": slot["samples"],
            "status": "predicted",
        }

    def predict_all(self, target_hour=None):
        results = {}
        for server_name in self._data:
            results[server_name] = self.predict(server_name, target_hour)
        return results

    def get_hourly_profile(self, server_name):
        server_data = self._data.get(server_name, {})
        profile = []
        for hour in range(24):
            slot = server_data.get(hour)
            if slot:
                profile.append({
                    "hour": hour,
                    "cpu_ema": slot["cpu_ema"],
                    "ram_ema": slot["ram_ema"],
                    "samples": slot["samples"],
                })
            else:
                profile.append({"hour": hour, "cpu_ema": None, "ram_ema": None, "samples": 0})
        return profile

    def pick_best_server(self, server_metrics):
        if not server_metrics:
            return None

        now_hour = (datetime.now().hour + 1) % 24
        scores = {}

        for name, metrics in server_metrics.items():
            if not metrics:
                continue

            current_cpu = metrics.get("cpu_percent", 0) or 0
            current_ram = (metrics.get("ram") or {}).get("percent", 0) or 0
            cpu_free = 100 - current_cpu
            ram_free_gb = (metrics.get("ram") or {}).get("free_gb", 0) or 0

            prediction = self.predict(name, now_hour)
            predicted_cpu = prediction.get("cpu_ema")
            predicted_ram = prediction.get("ram_ema")

            base_score = cpu_free * 0.5 + min(ram_free_gb * 2, 50) * 0.3

            if predicted_cpu is not None:
                predicted_penalty = predicted_cpu * 0.15
                base_score -= predicted_penalty

            scores[name] = round(base_score, 2)

        if not scores:
            return None

        return max(scores, key=scores.get)

    def clear(self, server_name=None):
        if server_name:
            self._data.pop(server_name, None)
        else:
            self._data = {}
        self._save()
