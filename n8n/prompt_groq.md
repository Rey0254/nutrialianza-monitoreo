# Prompt para el nodo HTTP Request → Groq API en N8N

Endpoint: `POST https://api.groq.com/openai/v1/chat/completions`
Header: `Authorization: Bearer {{ $env.GROQ_API_KEY }}`
Header: `Content-Type: application/json`

Modelo sugerido (gratuito, rápido): `llama-3.1-8b-instant`
(pueden usar `llama-3.3-70b-versatile` si necesitan mejor análisis y el
límite de 30 req/min lo permite)

## Body (JSON) del request

```json
{
  "model": "llama-3.1-8b-instant",
  "temperature": 0.2,
  "response_format": { "type": "json_object" },
  "messages": [
    {
      "role": "system",
      "content": "Eres un ingeniero de soporte de TI para NutriAlianza S.A., una planta de nutrición animal. Vas a recibir métricas de servidor y/o logs de eventos. Debes responder ÚNICAMENTE con un objeto JSON válido, sin texto adicional, sin markdown, sin backticks, siguiendo EXACTAMENTE este esquema: {\"severidad\": \"baja|media|critica\", \"resumen\": \"string\", \"causa_probable\": \"string\", \"recomendacion\": \"string\", \"accion_sugerida\": \"string o null\"}. Si no hay ninguna anomalía real, responde con severidad 'baja' y explica por qué está normal."
    },
    {
      "role": "user",
      "content": "Métricas actuales: CPU {{ $json.cpu }}%, RAM {{ $json.ram }}%, Disco {{ $json.disco }}%, Red {{ $json.red_mbps }} Mbps. Eventos de logs (últimos 5 min): {{ $json.eventos_logs }}. Analiza si hay una anomalía real, identifica la causa más probable correlacionando métricas y logs, y da una recomendación técnica concreta."
    }
  ]
}
```

## Notas clave

- `response_format: { "type": "json_object" }` es compatible con la API
  de Groq (es compatible con el formato de OpenAI) y es la forma más
  confiable de forzar JSON — más robusta que solo pedirlo en el prompt.
- Aun así, dejen el `system` prompt explícito pidiendo JSON puro, como
  respaldo por si el modelo no respeta `response_format` en algún caso.
- En el nodo siguiente de N8N (Function/Code), parseen la respuesta con
  `JSON.parse()` dentro de un `try/catch` — si Groq devuelve texto extra
  por error, no quieren que el flujo se caiga silenciosamente.
- Para el Nivel Intermedio/Avanzado, agreguen al `content` del mensaje
  `user` los datos reales que traen de Loki (errores 5xx, slow queries,
  intentos SSH) en vez de solo métricas — así la IA puede correlacionar
  múltiples fuentes, como pide el enunciado.

## Nodo Function para formatear el mensaje de Telegram

```javascript
const r = JSON.parse($json.choices[0].message.content);

const emojis = { baja: "🟢", media: "🟡", critica: "🔴" };

const texto =
`${emojis[r.severidad] || "⚪"} ALERTA ${r.severidad.toUpperCase()} - NutriAlianza S.A.

Resumen: ${r.resumen}
Causa probable: ${r.causa_probable}
Recomendación: ${r.recomendacion}
${r.accion_sugerida ? "Acción sugerida: " + r.accion_sugerida : ""}`;

return [{ json: { texto } }];
```

Ese `texto` es el campo que conectan al nodo **Telegram → Send Message**
(`chat_id = {{ $env.TELEGRAM_CHAT_ID }}`, `text = {{ $json.texto }}`).
