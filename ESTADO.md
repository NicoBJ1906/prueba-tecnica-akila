# Estado del proyecto · dónde retomar

Documento de continuidad entre sesiones de trabajo. **No forma parte de la
entrega a Akila**: es la libreta de a bordo. Última actualización: 2026-08-27.

---

## Lo único que falta para entregar

**Publicar el repositorio en GitHub.** El enunciado lo pide explícitamente
(«Entrega un repositorio de GitHub con todo el código y mándanos el enlace») y
es el único requisito literalmente incumplido. Hay 25 commits locales y ningún
remoto configurado.

Lo tiene que hacer Nicolás desde su cuenta:

```bash
gh repo create prueba-tecnica-akila --private --source=. --remote=origin
git push -u origin main
```

Nunca al repositorio de Akila, solo a la cuenta personal.

---

## Qué está hecho y verificado

Sobre un **clon limpio** (venv nuevo, `pip install -r requirements.txt`,
siguiendo solo el README): los dos ejercicios arrancan y las pruebas pasan.

| Requisito del enunciado | Estado |
|---|---|
| Ej1 · Qué automatizar con IA y qué no, con el «no» justificado | Sección 1 del README del ejercicio |
| Ej1 · Excel `Fecha \| Cliente \| Tipo \| Urgencia \| Acción \| Responsable` | Las 6 columnas en ese orden exacto |
| Ej1 · Sistema reutilizable y automatizado | `python -m triaje`, idempotente |
| Ej1 · Pasos para entregárselo a la persona | Sección 3 del README |
| Ej2 · Los 5 apartados | Los cinco |
| Ej2 · Código, no Excel ni Power BI | Python |
| Ej2 · README con comandos exactos | Probado literalmente en clon limpio |
| **Ej2 · Repositorio de GitHub** | **Pendiente** |

**198 pruebas** (168 de datos + 30 de interfaz), `ruff` limpio.

---

## Decisiones que hay que saber defender en la entrevista

1. **457 filas son 300 apartamentos.** El enunciado afirma que cada fila es un
   apartamento y no lo es. La regla de consolidación (vendido gana, y de los
   vendidos el más reciente) está documentada con las alternativas descartadas y
   sus consecuencias numéricas. Es el hallazgo central de la entrega.

2. **El CSV de correos también trae una trampa**: el correo de María López está
   duplicado literalmente (filas 1 y 8). El triaje lo detecta con la regla de
   deduplicación y lo deja escrito en el informe. El enunciado dice que a la
   persona «a veces se le duplica una entrada»: poder enseñar que el sistema no
   comete ese fallo es un buen momento de entrevista.

3. **De once etapas del triaje, una sola usa IA.** El resto es determinista. Se
   midió: reescribiendo los 15 correos con el mismo significado y otro
   vocabulario, la automatización cae del **80 % al 38 %** — pero el sistema no
   se equivoca ni una vez, manda a revisión humana lo que no entiende. Sin IA es
   correcto pero lento; la IA compra cobertura, no corrección. Los dos números
   salen del mismo pipeline y se pueden reproducir.

4. **Los hallazgos del dashboard se calculan con reglas, no con un modelo.**
   Mismo criterio. Son afirmaciones aritméticas comprobables en el gráfico de al
   lado, con umbrales que evitan reportar ruido (menos de 10 puntos de
   diferencia, o grupos de menos de 15 unidades, no se señalan).

5. **Los filtros estructurales son globales y persisten entre vistas.** No hay
   filtros distintos por pestaña a propósito: cambiar de vista y perder la
   selección rompe la comparación. La separación es por naturaleza del control
   (qué datos vs. cómo se dibujan), no por vista.

---

## Pendientes, por orden de valor

1. **Ejecutar el triaje con IA de verdad.** Hoy todo corre en modo `reglas`. Hay
   pruebas con proveedor simulado, pero ninguna ejecución real contra
   `claude-haiku`. Serían centavos con 15 correos. Necesita una `ANTHROPIC_API_KEY`.
   Sin esto, la respuesta honesta a «¿lo probaste con IA?» es no.

2. **Escalada selectiva al modelo.** Hoy, si se elige proveedor de IA, se llama
   al modelo para los 15 correos, incluidos los que las reglas resuelven
   perfectamente. Lo correcto es reglas primero y modelo solo cuando la
   confianza queda por debajo del umbral: en el experimento serían 7 llamadas en
   vez de 13. Son unas 20 líneas en `_clasificar` (`pipeline.py`) y convierte el
   discurso en «la IA es la segunda opinión, no el clasificador por defecto».

3. **Adversarial review pendiente.** Se lanzó y se canceló a mitad por consumo:
   no hay hallazgos, hay que rehacerlo entero. Cinco ángulos, en paralelo, cada
   uno con el papel de entrevistador de Akila buscando razones para no
   contratar, sin tocar el repo original y verificando cada afirmación:

   1. *Cumplimiento literal del enunciado* — frase por frase; clonar limpio y
      seguir solo el README, como haría el evaluador.
   2. *Corrección de las cifras* — recalcular todo con pandas sin usar el código
      del candidato; buscar casos donde la regla de consolidación sea
      indefendible; intentar que `metricas.insights()` afirme algo falso.
   3. *Calidad de código* — y sobre todo **pruebas de mutación**: romper el
      código a propósito en una copia (invertir un `>`, cambiar un orden,
      quitar una condición) y ver qué sobrevive con los tests en verde. Es lo
      que dice si la cobertura vale algo.
   4. *Ejercicio 1 y la tesis de la IA* — construir correos nuevos con jerga y
      faltas para reventar las reglas; atacar los guardrails; juzgar si «una
      sola etapa con IA» es criterio o excusa.
   5. *Seguridad* — secretos en el historial de git, qué datos personales salen
      del equipo, y CSVs hostiles contra el `file_uploader` nuevo (HTML sin
      escapar, CSV injection, tipos basura, codificaciones).

4. Repasar `docs/presentacion.md` con lo añadido en la última sesión (vista de
   torres, hallazgos, carga de otro export).

---

## Mapa del código

```
ejercicio1_triaje/
  triaje/pipeline.py     11 etapas; solo la 6 usa IA
  triaje/reglas.py       toda la lógica determinista
  triaje/proveedores.py  anthropic / gemini / reglas, intercambiables
  triaje/excel.py        4 hojas; «Seguimiento» tiene las 6 columnas exigidas
  config.toml            responsables, urgencia, remitentes automáticos

ejercicio2_dashboard/
  dashboard/etl.py       carga, validación, calidad, consolidación (acepta ruta o fichero abierto)
  dashboard/metricas.py  indicadores y hallazgos, funciones puras
  dashboard/app.py       solo compone y dibuja
```

**Regla de oro del ejercicio 2:** el cálculo nunca vive en `app.py`. Un
indicador nuevo son tres pasos: función pura en `metricas.py`, su test, y una
función `_grafico_*` en `app.py`.

---

## Trampas conocidas de la maqueta

Cosas que ya se rompieron una vez y tienen prueba que lo impide:

- **El CSS va en un f-string**: las llaves de CSS necesitan `{{ }}`. Olvidarlo
  tumba la app entera con un `NameError`.
- **Streamlit deja envolver sus columnas.** La columna de contenido lleva
  `flex-basis: 0` y la fila `flex-wrap: nowrap` por encima de 992 px: con
  `auto`, una vista con una tabla ancha partía la fila y el contenido caía
  debajo de la columna de vistas, dejando el centro en blanco.
- **El rótulo del indicador es una rejilla** cuya pista mide lo que el texto:
  centrarlo necesita `display: block`, no `justify-content`.
- **`scrollWidth` no delata un recorte con `text-overflow: ellipsis`.** Las
  pruebas miden el ancho real del texto con un `Range`.
- **`help=` en un botón** deja un segundo elemento de 0×0 en el DOM por cada
  botón. Descartado por eso.
- **Objetivo de maquetación:** el gráfico entero, con su eje, sin scroll desde
  **1280 × 720**. Cada línea que se añada a la cabecera se lo come.

---

## Cómo levantar el entorno

```bash
cd "/Users/nicolas/Documents/Prueba tecnica/prueba-tecnica-akila"
source .venv/bin/activate

streamlit run ejercicio2_dashboard/dashboard/app.py   # tablero
cd ejercicio1_triaje && python -m triaje              # triaje

pytest                                                # 198 pruebas
ruff check .
```

Las pruebas de interfaz necesitan `pip install -r requirements-dev.txt` y
`playwright install chromium`; sin eso se saltan solas.
