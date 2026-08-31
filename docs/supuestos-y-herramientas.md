# Supuestos, limitaciones y herramientas

Documento de acompañamiento a la entrega. Recoge tres cosas: **con qué se
desarrolló**, **qué se dio por supuesto** y **qué no hace esta solución**.

---

## 1. Herramientas y recursos utilizados

### Asistente de código

El desarrollo se hizo con **Claude Code (Anthropic)** como asistente, de forma
intensiva: implementación, batería de pruebas y documentación.

Conviene separar dos cosas, porque no se trabajaron igual:

| | Cómo se hizo |
|---|---|
| **Las decisiones** | Tomadas y justificadas a mano: la regla de consolidación y sus tres alternativas descartadas, qué se automatiza con IA y qué no, los umbrales de confianza y de relevancia, el orden de las etapas del pipeline, y qué se deja siempre a una persona. |
| **La implementación** | Escrita con el asistente, y **verificada de forma sistemática**, no aceptada por buena. |

Verificar lo que produce un asistente fue parte del trabajo, no un trámite:

- **247 pruebas automáticas**, incluidas adversariales y *golden tests* contra
  cifras calculadas a mano.
- **Un arnés de pruebas de mutación** (`docs/mutaciones.py`) que rompe el código
  a propósito de 19 formas y comprueba que las pruebas lo detecten. Las detecta
  las 19. La primera pasada solo cazaba 13 y **destapó cuatro huecos reales**.
- **Una revisión adversarial** de la entrega desde cinco ángulos —cumplimiento,
  datos, código, triaje y seguridad— buscando motivos para rechazarla. Encontró,
  entre otras cosas, un docstring que describía un comportamiento que el código
  ya no tenía, una validación que dejaba pasar texto donde esperaba números, y
  una ruta absoluta que impedía ejecutar un script fuera del equipo original.
- **Validación en un clon limpio**: se clonó el repositorio en una carpeta nueva
  y se siguió el README de arriba abajo, para comprobar que funciona en un equipo
  que no es el de desarrollo.

La postura es la misma que defiende el Ejercicio 1: **la herramienta acelera; el
criterio y la verificación no se delegan.**

### Modelos de lenguaje dentro del producto

Distinto de lo anterior: aquí se habla de la IA que usa el sistema al ejecutarse.

El triaje **funciona entero sin ningún modelo**. Clasifica con reglas
deterministas y produce el mismo Excel. La IA es opcional y se activa con una
variable de entorno.

| Proveedor | Estado |
|---|---|
| `reglas` | Por defecto. Sin credenciales, sin coste, sin latencia |
| `anthropic` | Claude Haiku 4.5, con salida estructurada |
| `gemini` | Gemini Flash, alternativa con plan gratuito |

**Por qué se deja desactivado por defecto:** el coste no es alto —unos 2-3
USD/mes para ~50 correos diarios con Haiku, y cero con el plan gratuito de
Gemini— pero **a bajo volumen no compensa**. Con quince o veinte correos al día,
las reglas resuelven el 80 % y lo que no resuelven va a revisión humana de todas
formas. El modelo empieza a pagarse cuando el volumen crece y la cola de revisión
manual se vuelve el cuello de botella. Es una decisión de tráfico, no de
tecnología.

Añadir otro proveedor —DeepSeek, un modelo local, el que sea— es implementar el
mismo contrato de `proveedores.py`: una clase con un método `clasificar` que
devuelve una `Clasificacion`. El resto del sistema no se entera.

### Otras herramientas

`pandas`, `Streamlit`, `Altair` y `openpyxl` para el producto. `pytest`, `ruff` y
`Playwright` para las pruebas. Cuatro dependencias en total para ejecutar la
solución; el resto son de desarrollo.

---

## 2. Supuestos

Decisiones tomadas donde el enunciado no daba una respuesta única. Todas están
documentadas en el sitio donde importan; aquí están reunidas.

### Sobre los datos de apartamentos

1. **Una unidad física se identifica por torre + piso + puerta.** El `id` cambia
   entre registros de la misma unidad, así que no sirve como identidad.
2. **Si hay alguna venta, la unidad está vendida**, y manda el registro de la
   venta más reciente. Una venta es un hecho fechado y con contraparte, y el
   fichero no trae ningún campo que marque anulaciones.
3. **Sin ninguna venta, manda el registro de `id` más alto**, por ser la versión
   más actual del inventario.
4. **El export es una foto del día en que se generó.** Por eso el ritmo comercial
   se mide sobre la ventana de datos disponible y no hasta la fecha actual: las
   semanas posteriores a la última venta no son semanas sin ventas, son semanas
   sin dato.

Las alternativas descartadas, con las cifras que habría dado cada una, están en
el [README del Ejercicio 2](../ejercicio2_dashboard/README.md#la-regla-de-consolidación).

### Sobre los correos

5. **La rúbrica de urgencia y el reparto de responsables son política de la
   empresa**, no criterio del sistema. Viven en `config.toml` y los aplican por
   igual las reglas y el modelo.
6. **Los asuntos legales o financieros los revisa siempre una persona**, con
   independencia de lo que clasifique el sistema.
7. **Actuar sobre el buzón es irreversible.** El sistema lee, pero no marca como
   leído, no archiva y no responde.

---

## 3. Limitaciones conocidas

Lo que esta entrega **no** hace, dicho antes de que lo pregunten.

### Del Ejercicio 1

- **El prompt no se ha ejecutado contra un modelo real.** Está construido,
  versionado e integrado, y probado contra respuestas simuladas —incluidas las
  inválidas, la caída del proveedor y los intentos de manipulación—, pero todas
  las cifras que se reportan salen del modo determinista, que es el peor caso.
- **Sin el hilo de conversación**, los correos que responden a algo anterior se
  clasifican con lo poco que se ve. El correo nº 2 de la muestra («Ok, muchas
  gracias») es el ejemplo: sin el hilo no se puede saber si cierra algo pendiente.
- **Los nombres se derivan de la dirección de correo** cuando el cliente no se
  firma en el cuerpo, así que pierden las tildes. Al conectar un buzón real con
  nombre para mostrar, esto desaparece.
- **Falta el disparador automático y el aviso al responsable.** El sistema lee el
  buzón y escribe el Excel; que se ejecute solo cada mañana es un `cron`, un flujo
  de n8n o el Programador de tareas, y avisar a quien le toca la fila está sin
  hacer.

### Del Ejercicio 2

- **25 unidades tienen un registro `Disponible` posterior a su venta.** La regla
  las cuenta como vendidas: son el 13,4 % del total vendido. Es la decisión más
  discutible de la entrega, y por eso el tablero permite ver la lectura
  alternativa.
- **El ritmo comercial ignora las semanas posteriores al último dato.** Reporta
  5,1 ventas/semana y 4,1 meses de inventario; anclado a la fecha actual serían
  2,8 y 7,4. Es deliberado (supuesto 4), pero conviene saberlo.
- **`app.py` concentra casi la mitad del repositorio.** Se defiende porque no
  calcula nada —es composición y estilos— pero es un fichero grande.

### De ambos

- **Los datos son ficticios y de una sola foto.** No hay forma de validar la
  regla de consolidación contra la realidad del proyecto; solo contra el propio
  fichero.
- **El arreglo de fondo de la calidad de datos no está aquí.** Un export que trae
  la misma unidad hasta siete veces con valores contradictorios es un problema del
  sistema que lo genera. El tablero consolida y documenta la regla, pero cualquier
  informe que salga de ese origen arrastrará la misma ambigüedad.
