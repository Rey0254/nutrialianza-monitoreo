# NutriAlianza S.A. — Sistema de Monitoreo Inteligente con Docker y IA

**BCD 7212 — Redes de Computadoras | II Cuatrimestre 2026**

Sistema de monitoreo de infraestructura para NutriAlianza S.A. (planta de nutrición animal), construido con contenedores Docker, que combina métricas de sistema (Prometheus), logs centralizados (Loki), automatización (N8N) y análisis inteligente de alertas mediante IA (Groq), con notificaciones en tiempo real a Telegram.

**Integrantes:** [Nombre 1] — [Rol], [Nombre 2] — [Rol]
**Nivel alcanzado:** Avanzado

---

## 1. Arquitectura del sistema

```
                    ┌──────────────────────────────────────────┐
                    │              VirtualBox VM                │
                    │           Ubuntu Server 22.04              │
                    │                                             │
  Internet ──SSH───▶│  ┌────────┐  ┌────────┐  ┌─────────────┐  │
  (puerto 2222)     │  │ Nginx  │  │ MySQL  │  │ Node         │  │
                     │  │ :80    │  │ :3306  │  │ Exporter     │  │
  Internet ──HTTP───▶│  └───┬────┘  └───┬────┘  │ :9100        │  │
  (puertos 80,443)   │      │           │        └──────┬───────┘  │
                     │      ▼           ▼               ▼          │
                     │  ┌────────────────────┐   ┌─────────────┐  │
                     │  │     Filebeat        │   │ Prometheus  │  │
                     │  └──────────┬──────────┘   │ :9090       │  │
                     │             ▼               └──────┬──────┘  │
                     │  ┌─────────────────┐               │        │
                     │  │    Logstash      │               │        │
                     │  └────────┬─────────┘               │        │
                     │           ▼                         │        │
                     │  ┌─────────────────┐                │        │
                     │  │      Loki        │◀───────────────┘ (Grafana)
                     │  │      :3100       │                        │
                     │  └────────┬─────────┘                        │
                     │           │          ┌─────────────┐         │
                     │           └─────────▶│  Grafana     │         │
                     │                      │  :3000       │         │
                     │                      └─────────────┘         │
                     │                                              │
                     │  ┌─────────────────┐    ┌──────────────┐    │
                     │  │  Blackbox        │    │     N8N       │    │
                     │  │  Exporter :9115  │◀───│     :5678     │    │
                     │  │ (ping/DNS/TCP/   │    │  (Schedule    │    │
                     │  │  HTTP checks)    │    │   cada 5 min) │    │
                     │  └─────────────────┘    └───────┬───────┘    │
                     └──────────────────────────────────┼────────────┘
                                                          ▼
                                                   ┌─────────────┐
                                                   │  Groq API    │
                                                   │ (LLM análisis│
                                                   │  de métricas)│
                                                   └──────┬───────┘
                                                          ▼
                                                   ┌─────────────┐
                                                   │  Telegram    │
                                                   │  (alertas)   │
                                                   └─────────────┘
```

**Flujo de datos:** Node Exporter y Blackbox Exporter recolectan métricas del sistema y checks de red → Prometheus las almacena → en paralelo, Nginx/MySQL/SSH generan logs → Filebeat los envía → Logstash los transforma → Loki los indexa → Grafana visualiza ambas fuentes. Cada 5 minutos, N8N consulta Prometheus, envía las métricas a Groq (IA) para análisis, y publica el diagnóstico en Telegram.

---

## 2. Stack de servicios (11 contenedores)

| Servicio | Imagen | Puerto | Función |
|---|---|---|---|
| `nginx` | nginx:stable | 80, 443 | Servidor web / reverse proxy |
| `mysql` | mysql:8.0 | 3306 | Base de datos operativa (~350K registros) |
| `node-exporter` | prom/node-exporter | 9100 | Métricas de sistema (CPU/RAM/disco/red) |
| `blackbox-exporter` | prom/blackbox-exporter | 9115 | Health checks HTTP, ping, DNS, TCP |
| `prometheus` | prom/prometheus | 9090 | Almacenamiento de métricas (modelo *pull*) |
| `loki` | grafana/loki | 3100 | Almacenamiento de logs |
| `logstash` | build local | 5044 (interno) | Puente Filebeat → Loki |
| `filebeat` | elastic/filebeat | — | Recolector de logs (Nginx/MySQL/SSH) |
| `grafana` | grafana/grafana | 3000 | Visualización (dashboards) |
| `n8n` | n8nio/n8n | 5678 | Orquestación de alertas con IA |

Adicional (a nivel de host, no contenedor): **fail2ban**, **UFW**, **vnstat**.

---

## 3. Requisitos previos

- VirtualBox 7.x con una VM Ubuntu Server 22.04 (mínimo 4 vCPU / 6 GB RAM / 40 GB disco).
- Docker Engine + Docker Compose v2 instalados en la VM.
- Cuenta gratuita en [Groq Console](https://console.groq.com) con una API key.
- Un bot de Telegram creado vía [@BotFather](https://t.me/BotFather) (token) y su Chat ID de destino.

---

## 4. Instalación paso a paso

### 4.1 Clonar el repositorio dentro de la VM

```bash
git clone <URL_DEL_REPOSITORIO> nutrialianza-monitoreo
cd nutrialianza-monitoreo
```

### 4.2 Configurar variables de entorno

```bash
cp .env.example .env
nano .env
```

Completar como mínimo:
```
MYSQL_ROOT_PASSWORD=<su_password>
MYSQL_DATABASE=nutrialianza_db
MYSQL_USER=nutriapp
MYSQL_PASSWORD=<su_password>
GROQ_API_KEY=<su_api_key_de_groq>
TELEGRAM_BOT_TOKEN=<su_token_de_botfather>
TELEGRAM_CHAT_ID=<su_chat_id>
GF_ADMIN_USER=admin
GF_ADMIN_PASSWORD=<su_password>
```

### 4.3 Levantar el stack

```bash
docker compose up -d --build
```

El flag `--build` es necesario la primera vez porque Logstash usa una imagen construida localmente (instala el plugin `logstash-output-loki`).

Verificar que los 11 contenedores estén activos:
```bash
docker compose ps
```

### 4.4 Importar la base de datos

```bash
docker compose exec -T mysql mysql -u root -p"$MYSQL_ROOT_PASSWORD" nutrialianza_db < mysql/nutrialianza_db.sql
```

(Puede tardar 1–3 minutos por el volumen de datos.)

### 4.5 Configurar N8N

1. Abrir `http://localhost:5678` (o `http://<IP_DE_LA_VM>:5678`).
2. Crear la cuenta de owner en el primer acceso.
3. Importar el flujo desde `n8n/workflow.json` (si se exportó) o reconstruirlo siguiendo `n8n/prompt_groq.md`.
4. Verificar las credenciales de Telegram dentro del nodo "Send a text message".
5. Publicar el workflow (botón **Publish**) para que corra automáticamente cada 5 minutos.

### 4.6 Configurar Grafana

1. Abrir `http://localhost:3000` (usuario/password del `.env`).
2. **Connections → Data sources → Add data source**:
   - Prometheus: URL `http://prometheus:9090`
   - Loki: URL `http://loki:3100`
3. Importar el dashboard **Node Exporter Full** (ID `1860` desde grafana.com) y seleccionar el data source Prometheus.
4. El dashboard de logs (**NutriAlianza - Logs y Seguridad**) ya viene definido en `grafana/dashboards/` (o se reconstruye siguiendo la Memoria de Implementación del informe).

---

## 5. Acceso a los servicios

| Servicio | URL local | Notas |
|---|---|---|
| Sitio web | http://localhost/ | Health check en `/health` |
| Prometheus | http://localhost:9090 | `/targets` para ver el estado de los scrapes |
| Grafana | http://localhost:3000 | admin / (ver `.env`) |
| N8N | http://localhost:5678 | Cuenta creada en el primer acceso |
| MySQL | localhost:3306 | root / (ver `.env`) |

Si se accede desde fuera de la VM (por ejemplo, el profesor evaluando en su propia máquina), configurar el **reenvío de puertos** de VirtualBox (NAT) para los puertos: 22, 80, 443, 3000, 5678, 9090.

---

## 6. Puntos de monitoreo implementados

| # | Punto de monitoreo | Mecanismo |
|---|---|---|
| 1 | Ping / latencia | Blackbox Exporter (módulo `icmp_ping`) contra 8.8.8.8 |
| 2 | Resolución DNS | Blackbox Exporter (módulo `dns_check`) |
| 3 | Health check HTTP | Blackbox Exporter (módulo `http_2xx`) contra `nginx/health` |
| 4 | Puertos TCP críticos | Blackbox Exporter (módulo `tcp_connect`) — Nginx:80, MySQL:3306, N8N:5678 |
| 5 | Ancho de banda | vnstat (interfaz `enp0s3`, a nivel de host) |
| 6 | CPU / RAM / disco | Prometheus + Node Exporter |
| 7 | Errores de Nginx | Filebeat → Logstash → Loki (`log_type=error`) |
| 8 | Slow queries de MySQL | Filebeat → Logstash → Loki (`log_type=slow_query`, umbral 2s) |
| 9 | Intentos SSH / autenticación | Filebeat → Logstash → Loki (`service=auth`) + fail2ban |

---

## 7. Flujo de alertas con IA

Cada 5 minutos, el workflow de N8N:
1. Consulta a Prometheus: CPU, RAM, disco, ancho de banda y estado del health check web (`probe_success`).
2. Combina las 5 métricas en un solo objeto JSON.
3. Envía el contexto a la API de Groq (modelo `llama-3.1-8b-instant`), pidiendo un análisis estructurado (`severidad`, `resumen`, `causa_probable`, `recomendacion`) en formato JSON forzado.
4. Formatea la respuesta y la envía por Telegram al chat configurado.

El prompt completo usado se documenta en `n8n/prompt_groq.md`.

---

## 8. Escenarios de prueba (emulación de fallos)

| Escenario | Comando | Resultado esperado |
|---|---|---|
| Saturación HTTP Nginx | `ab -n 5000 -c 200 http://localhost/` | Aumento de CPU/latencia visible en Grafana |
| Saturación de conexiones MySQL | `mysqlslap --concurrency=200 --iterations=3 --query="..." --create-schema=nutrialianza_db` | Error `1040 Too many connections`, slow queries registradas |
| Caída del servicio web | `docker compose stop nginx` | `probe_success=0` en Prometheus, alerta CRÍTICA de la IA en Telegram |

---

## 9. Estructura del repositorio

```
nutrialianza-monitoreo/
├── docker-compose.yml
├── .env.example
├── README.md
├── nginx/
│   └── nginx.conf
├── mysql/
│   └── nutrialianza_db.sql
├── prometheus/
│   ├── prometheus.yml
│   └── blackbox.yml
├── filebeat/
│   └── filebeat.yml
├── logstash/
│   ├── Dockerfile
│   └── logstash.conf
└── n8n/
    └── prompt_groq.md
```

---

## 10. Notas de seguridad

- El archivo `.env` **no** se incluye en el repositorio (ver `.gitignore`); solo `.env.example` con placeholders.
- El servidor implementa hardening básico: autenticación SSH solo por llave pública, firewall UFW con política *deny-by-default*, fail2ban contra fuerza bruta SSH, y actualizaciones de seguridad automáticas.
- Las credenciales de Groq y Telegram usadas durante el desarrollo fueron regeneradas antes de la entrega final.
