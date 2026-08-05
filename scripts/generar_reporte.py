#!/usr/bin/env python3
"""
Generador de reportes de métricas históricas para NutriAlianza S.A.
Exporta a CSV el histórico de CPU, RAM, disco y red desde Prometheus,
más un resumen de eventos de logs desde Loki.
Uso: python3 generar_reporte.py [horas_atras]  (por defecto 24)
"""
import sys, json, csv, time, urllib.request, urllib.parse
from datetime import datetime, timedelta

PROM = "http://localhost:9090"
LOKI = "http://localhost:3100"
horas = int(sys.argv[1]) if len(sys.argv) > 1 else 24

end = int(time.time())
start = end - horas * 3600
step = "300"  # 5 minutos

def prom_range(query):
    params = urllib.parse.urlencode({"query": query, "start": start, "end": end, "step": step})
    url = f"{PROM}/api/v1/query_range?{params}"
    with urllib.request.urlopen(url, timeout=15) as r:
        data = json.load(r)
    result = data.get("data", {}).get("result", [])
    return {int(float(v[0])): float(v[1]) for v in result[0]["values"]} if result else {}

def loki_count(query):
    params = urllib.parse.urlencode({
        "query": query,
        "start": str(start * 1_000_000_000),
        "end": str(end * 1_000_000_000),
    })
    url = f"{LOKI}/loki/api/v1/query_range?{params}"
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            data = json.load(r)
        return sum(len(s["values"]) for s in data.get("data", {}).get("result", []))
    except Exception:
        return 0

print(f"Generando reporte de las últimas {horas} horas...")

cpu = prom_range('100 - (avg(rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)')
ram = prom_range('(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100')
disco = prom_range('(1 - (node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"})) * 100')
red = prom_range('sum(rate(node_network_receive_bytes_total{device!="lo"}[5m])) * 8 / 1000000')

timestamps = sorted(set(cpu) | set(ram) | set(disco) | set(red))

fecha_str = datetime.now().strftime("%Y%m%d_%H%M%S")
out_dir = "/home/nicoyrey/nutrialianza-monitoreo/reportes"
import os
os.makedirs(out_dir, exist_ok=True)

csv_path = f"{out_dir}/reporte_metricas_{fecha_str}.csv"
with open(csv_path, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["timestamp", "fecha_hora", "cpu_pct", "ram_pct", "disco_pct", "red_mbps"])
    for ts in timestamps:
        fh = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
        w.writerow([ts, fh, cpu.get(ts, ""), ram.get(ts, ""), disco.get(ts, ""), red.get(ts, "")])

nginx_err = loki_count('count_over_time({service="nginx", log_type="error"}[' + str(horas) + 'h])')
slow_q = loki_count('count_over_time({service="mysql", log_type="slow_query"}[' + str(horas) + 'h])')
ssh_fail = loki_count('count_over_time({service="auth"} |= "Failed password" [' + str(horas) + 'h])')

resumen_path = f"{out_dir}/resumen_eventos_{fecha_str}.csv"
with open(resumen_path, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["metrica", "valor"])
    w.writerow(["periodo_horas", horas])
    w.writerow(["cpu_promedio_pct", round(sum(cpu.values())/len(cpu), 2) if cpu else "N/A"])
    w.writerow(["cpu_maximo_pct", round(max(cpu.values()), 2) if cpu else "N/A"])
    w.writerow(["ram_promedio_pct", round(sum(ram.values())/len(ram), 2) if ram else "N/A"])
    w.writerow(["ram_maximo_pct", round(max(ram.values()), 2) if ram else "N/A"])
    w.writerow(["errores_nginx_total", nginx_err])
    w.writerow(["slow_queries_mysql_total", slow_q])
    w.writerow(["intentos_ssh_fallidos_total", ssh_fail])
    w.writerow(["puntos_de_datos_recolectados", len(timestamps)])

print(f"Reporte detallado: {csv_path}")
print(f"Resumen ejecutivo: {resumen_path}")
print(f"Puntos de datos: {len(timestamps)}")
