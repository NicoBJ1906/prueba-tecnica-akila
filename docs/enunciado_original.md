# Akila · Prueba técnica (pre-entrevista)

**Puesto:** IA y optimización de procesos · Bogotá

Esta prueba tiene **dos ejercicios**. Léelos con calma, trabaja con los ficheros adjuntos y prepárate para **presentar tus resultados antes del día de la entrevista** y **responder dudas el día de la entrevista**. No hay una única respuesta correcta: evaluamos cómo piensas, no la estética del resultado.

---

## Ejercicio 1 — Triaje de correos y volcado a seguimiento

### Contexto

En Akila, una persona dedica alrededor de **2 horas al día** a leer los correos entrantes de clientes, clasificarlos y volcarlos a un Excel de seguimiento.

**Cómo funciona el proceso hoy:**

Cada mañana, la persona abre el correo y revisa los mensajes uno a uno. Por cada correo decide de qué cliente es, qué tipo de petición es (consulta, incidencia, pedido, reclamación) y cómo de urgente es. Luego abre el Excel de seguimiento y añade una fila a mano con esos datos, más la acción a tomar y quién es el responsable. Cuando termina, marca el correo como leído y pasa al siguiente. Los correos ambiguos los deja para el final o pregunta a un compañero. A veces se le duplica una entrada o se le olvida rellenar la fecha.

### Material adjunto

- **`correos_clientes.csv`** — una muestra de 15 correos de cliente.

### Entrega

1. **Qué automatizarías con IA y qué no.** Justifica especialmente el "no".
2. **El ejemplo real** de cómo quedaría el proceso ya optimizado (el Excel relleno, un esquema del flujo, un prompt funcionando… lo que elijas). El excel debe tener las columnas: `Fecha | Cliente | Tipo | Urgencia | Acción | Responsable`. Debe ser un sistema reutilizable y lo más automatizado posible.
3. La explicación de qué pasos se deben seguir para darle este proceso a la persona que hace este proceso automatizado.

**Para terminar:** imagina que te decimos *"necesito que ayudes a optimizar este proceso, ¿cómo lo harías?"*. Prepárate para explicárnoslo el día de la entrevista.

---

## Ejercicio 2 — Dashboard de ventas de apartamentos

Construye la solución **con código** y entréganos un **repositorio de GitHub** que podamos clonar y ejecutar.

### Contexto

Akila desarrolla proyectos de vivienda en Bogotá. Te entregamos un export de la cartera de apartamentos de uno de nuestros proyectos (es ficticio): cada fila es un apartamento, con su tipo, precio en pesos colombianos (COP), estado (vendido o disponible), forma de pago y fechas de venta y de entrega.

El fichero es **`apartamentos_akila.csv`** (457 apartamentos).

### Los datos

| Columna | Qué contiene |
|---|---|
| `apartamento`, `torre`, `piso`, `numero_puerta` | Identificación y ubicación del apartamento |
| `tipo_apartamento` | Apartaestudio, 1 Alcoba, 2 Alcobas, 3 Alcobas, Penthouse |
| `area_m2` | Metros cuadrados |
| `precio_cop` | Precio de venta en pesos colombianos |
| `estado` | Vendido o Disponible |
| `fecha_venta` | Fecha de venta (solo si está vendido) |
| `fecha_entrega` | Fecha de entrega de la obra |
| `forma_pago` | Contado o Crédito (solo vendidos) |
| `porcentaje_credito` | % financiado a crédito (0 si es de contado) |
| `monto_credito_cop`, `monto_contado_cop` | Parte pagada a crédito y parte en efectivo |

### Qué tienes que construir

Un dashboard que a dirección le sirva para entender cómo va el proyecto de un vistazo. Debe incluir estos apartados:

1. **Ventas por semana** — número o valor de apartamentos vendidos por semana, según la fecha de venta.
2. **Apartamentos vendidos** — total vendido.
3. **Tipos de apartamento vendidos** — tabla con cada tipo, cuántos se han vendido y qué **%** representa sobre el total de ventas.
4. **Apartamentos disponibles** — cuántos quedan libres.
5. **Variedad de producto** — cuántos tipos de apartamento distintos hay en el proyecto.

### Cómo entregarlo (importante)

- **Entrega un repositorio de GitHub** con todo el código de la solución y mándanos el enlace.
- **Debe ser código, no Excel ni Power BI.** Elige el lenguaje y las librerías que domines o que te sirvan (Python, JavaScript, R, lo que quieras).
- **El README del repositorio es obligatorio** y debe incluir:
  - Qué hace la solución.
  - Los comandos exactos para ejecutarlo y ver el dashboard. Recomendado incluirlo en el Readme del proyecto.

  Tenemos que poder **clonar el repo y hacerlo funcionar siguiendo solo el README**.

**Para terminar:** prepárate para responder *"necesito que ayudes a optimizar este proceso de reporting, ¿cómo lo harías?"*.
