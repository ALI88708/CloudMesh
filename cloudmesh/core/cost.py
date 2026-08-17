import json, os

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")

PRICING = {
    "aws": {
        "t2.micro": {"cpu": 1, "ram": 1, "price_month": 8.47},
        "t2.small": {"cpu": 1, "ram": 2, "price_month": 16.94},
        "t2.medium": {"cpu": 2, "ram": 4, "price_month": 33.88},
        "t3.micro": {"cpu": 2, "ram": 1, "price_month": 8.47},
        "t3.small": {"cpu": 2, "ram": 2, "price_month": 16.94},
        "t3.medium": {"cpu": 2, "ram": 4, "price_month": 33.88},
        "m5.large": {"cpu": 2, "ram": 8, "price_month": 96.0},
        "m5.xlarge": {"cpu": 4, "ram": 16, "price_month": 192.0},
        "c5.large": {"cpu": 2, "ram": 4, "price_month": 77.0},
        "c5.xlarge": {"cpu": 4, "ram": 8, "price_month": 154.0},
        "g4dn.xlarge": {"cpu": 4, "ram": 16, "price_month": 186.0, "gpu": "T4"},
        "g4dn.2xlarge": {"cpu": 8, "ram": 32, "price_month": 312.0, "gpu": "T4"},
        "p3.2xlarge": {"cpu": 8, "ram": 61, "price_month": 967.0, "gpu": "V100"},
        "p3.8xlarge": {"cpu": 32, "ram": 244, "price_month": 3868.0, "gpu": "V100x8"},
    },
    "gcp": {
        "e2-micro": {"cpu": 0.25, "ram": 1, "price_month": 6.11},
        "e2-small": {"cpu": 0.5, "ram": 2, "price_month": 12.22},
        "e2-medium": {"cpu": 1, "ram": 4, "price_month": 16.57},
        "n2-standard-2": {"cpu": 2, "ram": 8, "price_month": 67.29},
        "n2-standard-4": {"cpu": 4, "ram": 16, "price_month": 134.58},
        "a2-highgpu-1g": {"cpu": 12, "ram": 85, "price_month": 367.0, "gpu": "A100"},
    },
    "azure": {
        "B1s": {"cpu": 1, "ram": 1, "price_month": 7.59},
        "B2s": {"cpu": 2, "ram": 4, "price_month": 30.37},
        "D2s_v3": {"cpu": 2, "ram": 8, "price_month": 70.08},
        "D4s_v3": {"cpu": 4, "ram": 16, "price_month": 140.16},
        "NC6": {"cpu": 6, "ram": 56, "price_month": 540.0, "gpu": "K80"},
    },
    "do": {
        "s-1vcpu-1gb": {"cpu": 1, "ram": 1, "price_month": 6.0},
        "s-1vcpu-2gb": {"cpu": 1, "ram": 2, "price_month": 12.0},
        "s-2vcpu-4gb": {"cpu": 2, "ram": 4, "price_month": 24.0},
        "g-2vcpu-8gb": {"cpu": 2, "ram": 8, "price_month": 48.0},
        "gpu-a100x1": {"cpu": 12, "ram": 64, "price_month": 645.0, "gpu": "A100"},
    }
}

DISK_PRICING = {
    "aws": 0.10,
    "gcp": 0.04,
    "azure": 0.05,
    "do": 0.02,
    "hetzner": 0.05
}

BANDWIDTH_PRICING = {
    "aws": 0.09,
    "gcp": 0.085,
    "azure": 0.087,
    "do": 0.01,
    "hetzner": 0.01
}

def list_instances(provider="aws"):
    return PRICING.get(provider.lower(), {})

def estimate_cost(provider, instance_type, hours=730, disk_gb=0, bandwidth_gb=0):
    provider = provider.lower()
    instances = PRICING.get(provider, {})
    inst = instances.get(instance_type)
    if not inst:
        return f"Instance '{instance_type}' not found for {provider}"

    monthly = inst["price_month"]
    hourly_cost = monthly / 730.0
    actual_cost = hourly_cost * hours
    disk_cost = disk_gb * DISK_PRICING.get(provider, 0.05) * (hours / 730.0)
    bw_cost = bandwidth_gb * BANDWIDTH_PRICING.get(provider, 0.05)
    total = actual_cost + disk_cost + bw_cost

    return {
        "provider": provider,
        "instance": instance_type,
        "cpu": inst.get("cpu"),
        "ram_gb": inst.get("ram"),
        "gpu": inst.get("gpu"),
        "compute_cost": round(actual_cost, 2),
        "disk_cost": round(disk_cost, 2),
        "bandwidth_cost": round(bw_cost, 2),
        "total_cost": round(total, 2),
        "period_hours": hours,
        "monthly_equivalent": round(monthly + disk_cost * (730 / max(hours, 1)), 2)
    }

def compare_all(instance_type, hours=730):
    results = []
    for provider in PRICING:
        if instance_type in PRICING[provider]:
            est = estimate_cost(provider, instance_type, hours)
            if isinstance(est, dict):
                results.append(est)
    results.sort(key=lambda x: x.get("total_cost", 9999))
    return results

def cheapest_instance(cpu=None, ram=None, provider=None):
    results = []
    for prov, instances in PRICING.items():
        if provider and prov != provider:
            continue
        for name, info in instances.items():
            if cpu and info.get("cpu", 0) < cpu:
                continue
            if ram and info.get("ram", 0) < ram:
                continue
            results.append({
                "provider": prov,
                "instance": name,
                "cpu": info["cpu"],
                "ram": info["ram"],
                "price_month": info["price_month"],
                "gpu": info.get("gpu")
            })
    results.sort(key=lambda x: x["price_month"])
    return results[:10]
