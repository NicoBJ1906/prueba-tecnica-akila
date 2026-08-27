# Informe de ejecución del triaje

Generado el 2026-08-27 00:10.

## Qué pasó con cada correo

| Etapa | Correos |
|---|---|
| Leídos del origen | 15 |
| Ya procesados en ejecuciones previas | 0 |
| Descartados antes de clasificar | 2 |
| Filas generadas en el seguimiento | 15 |
|   · resueltas automáticamente | 12 |
|   · sin acción requerida | 1 |
|   · enviadas a revisión humana | 2 |


**Automatización efectiva: 80 %** de las filas quedaron listas sin intervención.

## Descartes (y por qué)

| Regla | Correos |
|---|---|
| deduplicación | 1 |
| remitentes automáticos | 1 |


Detalle:

| Remitente | Asunto | Motivo |
|---|---|---|
| maria.lopez@gmail.com | Consulta apartamento Torre 2 | El mismo mensaje ya entró hoy desde este remitente. |
| notificaciones@bancolombia.com.co | Tu extracto de julio está disponible | Remitente o contenido automático (coincide con «notificaciones@»). |


## Cola de revisión humana

| Cliente | Tipo | Urgencia | Motivo |
|---|---|---|---|
| Carlos Medina | Consulta | Baja | Confianza 0.50 por debajo del umbral 0.70. El correo no aporta contexto suficiente (sin asunto claro, sin apartamento y sin tema identificable). Clasificación por palabras clave, sin modelo de lenguaje. |
| Jorge Valencia | Reclamación | Media | Asunto con implicación legal o financiera: lo decide una persona. (detectado: «desistir»). Clasificación por palabras clave, sin modelo de lenguaje. |


## Distribución del trabajo

**Por tipo**

| Tipo | Filas |
|---|---|
| Consulta | 6 |
| Incidencia | 1 |
| Pedido | 5 |
| Reclamación | 3 |


**Por urgencia**

| Urgencia | Filas |
|---|---|
| Alta | 2 |
| Baja | 6 |
| Media | 7 |


**Por responsable**

| Responsable | Filas |
|---|---|
| Cartera | 1 |
| Comercial | 2 |
| Gerencia Comercial | 1 |
| Jurídica | 2 |
| Posventa y Obra | 3 |
| Servicio al Cliente | 5 |
| — | 1 |


## Coste y rendimiento

| Métrica | Valor |
|---|---|
| Clasificador | reglas |
| Llamadas al modelo | 0 |
| Tokens de entrada | 0 |
| Tokens de salida | 0 |
| Coste estimado | USD 0 (sin llamadas de pago) |
| Duración | 0.0 s |

