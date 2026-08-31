# Prueba técnica Akila · IA y optimización de procesos

Solución a los dos ejercicios, por **Nicolás Bejarano**.

**[▶ Ver el dashboard funcionando](https://prueba-tecnica-akila.streamlit.app)** ·
sin instalar nada

![Dashboard de ventas](docs/capturas/dashboard-general.png)

---

## Los dos ejercicios

| | Qué resuelve | Cómo se ejecuta |
|---|---|---|
| **1 · [Triaje de correos](ejercicio1_triaje/)** | 2 h diarias de leer y copiar correos a un Excel → 15 min de revisar solo lo dudoso | `python -m triaje` |
| **2 · [Dashboard de ventas](ejercicio2_dashboard/)** | Un tablero para dirección, sobre datos que resultaron no estar limpios | `streamlit run ejercicio2_dashboard/dashboard/app.py` |

## Empezar

```bash
git clone https://github.com/NicoBJ1906/prueba-tecnica-akila.git
cd prueba-tecnica-akila
python3 -m venv .venv && source .venv/bin/activate    # Windows: py -m venv .venv && .venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Y ya. **No hace falta ninguna clave de API ni ninguna cuenta.**

<details>
<summary><b>Instrucciones paso a paso</b> — si no tienes Python o es tu primera vez con una terminal</summary>

<br>

### Paso 0 · Comprueba que tienes Python

Hace falta **Python 3.11 o superior**. Para saber si lo tienes, abre una terminal
(en Windows, *PowerShell*; en macOS, *Terminal*) y escribe:

```bash
python3 --version     # en Windows:  py --version
```

Si responde algo como `Python 3.12.4`, listo. Si dice que no encuentra la orden o
sale una versión menor que 3.11, instálalo desde
[python.org/downloads](https://www.python.org/downloads/). En Windows, marca la
casilla **«Add Python to PATH»** durante la instalación.

### Paso 1 · Descarga el proyecto

```bash
git clone https://github.com/NicoBJ1906/prueba-tecnica-akila.git
cd prueba-tecnica-akila
```

Si no tienes `git`, puedes bajar el ZIP desde GitHub («Code» → «Download ZIP»),
descomprimirlo y entrar en la carpeta.

### Paso 2 · Prepara el entorno

Esto crea una carpeta `.venv` con las cuatro librerías que usa el proyecto, sin
tocar el resto de tu equipo.

**macOS / Linux**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**Windows (PowerShell)**

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Sabrás que ha funcionado porque el nombre `(.venv)` aparece al principio de la
línea de la terminal. **Si cierras la terminal, hay que repetir solo la línea de
`activate`**, no la instalación.

</details>

<details>
<summary><b>Si algo no funciona</b> — los seis errores habituales y su solución</summary>

<br>

| Lo que ves | Qué pasa |
|---|---|
| `command not found: python3` | Python no está instalado o no está en el PATH. En Windows usa `py` en lugar de `python3` |
| `No module named pandas` | Falta activar el entorno: repite la línea de `activate` del paso 2 |
| `.venv\Scripts\Activate.ps1 no se puede cargar` | PowerShell bloquea scripts. Ejecuta `Set-ExecutionPolicy -Scope Process RemoteSigned` y repite |
| `No se encontró el fichero de datos` | Estás en la carpeta equivocada. El dashboard se lanza desde la raíz; el triaje desde `ejercicio1_triaje` |
| `No se pudo escribir en …seguimiento.xlsx` | Tienes el Excel abierto. Ciérralo y repite: no se pierde ningún correo |
| El puerto 8501 está ocupado | `streamlit run … --server.port 8502` |

</details>

---

## Ejercicio 1 · El triaje

```bash
cd ejercicio1_triaje
python -m triaje
```

```
  Correos leídos ................. 15
  Filas en el seguimiento ........ 15
    · automáticas ................ 12     ← listas, sin tocar nada
    · para revisión humana ....... 2      ← lo dudoso y lo legal
```

Genera `salida/seguimiento.xlsx` con cuatro hojas —**Seguimiento** (las 6 columnas
del enunciado), **Para revisar**, **Descartados** y **Resumen**— más un informe de
lo que hizo y por qué.

Se puede ejecutar mil veces: **no duplica filas**.

> **También lee un buzón real.** Con tres variables de entorno se conecta por IMAP
> a Gmail, Outlook o el que sea, y vuelca al Excel cada minuto. Solo lee: no marca
> como leído ni archiva.
> [Cómo se configura →](ejercicio1_triaje/README.md#del-csv-a-un-buzón-real)

## Ejercicio 2 · El dashboard

```bash
streamlit run ejercicio2_dashboard/dashboard/app.py
```

Se abre en `http://localhost:8501`. Cuatro vistas: **Ventas**, **Producto**,
**Torres** y **Datos**.

| Vendidos | Disponibles | Valor vendido | Variedad |
|:---:|:---:|:---:|:---:|
| **209** | **91** | **$137,7 MM** | **5 tipos** |

---

## Las dos decisiones que definen esta entrega

**1 · La IA clasifica; no decide y no responde.** De las once etapas del triaje,
una sola usa un modelo. No se automatiza responder al cliente, decidir sobre
desistimientos, asignar responsables ni definir qué es urgente.

**2 · Los datos no estaban limpios, y eso cambia las cifras.** El export dice
traer 457 apartamentos. **Son 300.**

| | Leyendo el fichero tal cual | Consolidado |
|---|---|---|
| Vendidos | 271 | **209** |
| Disponibles | 186 | **91** |

Reportar «271 vendidos» a dirección sería inventar un 30 % de ventas.

<details>
<summary><b>El razonamiento completo de las dos</b></summary>

<br>

### 1. La IA clasifica; no decide y no responde

De las once etapas del triaje, **una sola** usa un modelo de lenguaje. No por
prudencia decorativa, sino porque cada etapa determinista es más barata, más
rápida y explicable ante un cliente enfadado. Extraer un número de apartamento
con una expresión regular acierta el 100 % y cuesta cero; pedírselo a un modelo
es pagar por una respuesta peor.

Lo que **no** se automatiza: responder al cliente, decidir sobre desistimientos
y devoluciones, asignar responsables y definir qué es urgente. Los dos primeros
por coste de error asimétrico —automatizar bien ahorra dos minutos, automatizar
mal cuesta un pleito—; los dos últimos porque son política de la empresa y viven
en una tabla que la empresa mantiene, no en el criterio variable de un modelo.

El razonamiento completo, caso por caso, está en el
[README del Ejercicio 1](ejercicio1_triaje/README.md#1-qué-automatizaría-con-ia-y-qué-no).

### 2. Los datos del Ejercicio 2 no estaban limpios, y eso cambia las cifras

109 unidades aparecen repetidas con tipo, área, precio y estado contradictorios;
47 figuran vendidas más de una vez en fechas distintas.

El
dashboard le dedica una vista entera —«Calidad»—, documenta la
regla que aplica y permite comparar ambas lecturas con un selector, porque
la regla es discutible y quien decide debe poder verla.

El detalle, con las alternativas descartadas, está en el
[README del Ejercicio 2](ejercicio2_dashboard/README.md#lo-primero-que-hay-que-saber-sobre-estos-datos).

</details>

---

## Las pruebas

```bash
pytest                       # 242 pruebas
python docs/mutaciones.py    # rompe el código a propósito y comprueba que las pruebas lo noten
```

**El arnés de mutación detecta las 19 de 19.** Que las pruebas pasen no demuestra
que sirvan; esto sí.

<details>
<summary><b>Qué cubren exactamente</b></summary>

<br>

También desde la raíz: `pytest` recoge las de cada ejercicio por su ruta, y
lanzado desde dentro de una carpeta solo encuentra las de esa.

```bash
pytest
```

212 pruebas: unitarias, de integración, *golden tests* contra cifras verificadas
a mano y adversariales (intentos de manipulación del clasificador, respuestas
inválidas del modelo, caída del proveedor, entradas malformadas).

**Que las pruebas pasen no demuestra que sirvan.** Para comprobarlo hay un arnés
de mutación en `docs/mutaciones.py`: rompe el código a propósito de 19 formas
distintas —invierte la prioridad de la consolidación, se queda con la venta más
antigua, calcula el porcentaje sobre el total equivocado, desactiva una
validación— y verifica que las pruebas lo detecten.

```bash
python docs/mutaciones.py    # trabaja sobre una copia; no toca el repo
```

**Detecta las 19.** No siempre fue así: la primera pasada cazaba 13 y destapó
cuatro huecos reales —entre ellos un `assert` tautológico que seguía a la
constante que pretendía comprobar—. Las últimas tres en caer fueron los umbrales
que evitan reportar ruido en los hallazgos, el filtro de unidades sin fecha de
entrega y la composición de pago, que sumaba disponibles. Todas están cubiertas
ahora.

Hay además 30 pruebas de interfaz —242 en total— que abren el dashboard en un navegador real y
comprueban la maquetación y el comportamiento: que el gráfico entre entero en
pantalla, que ningún indicador se corte, que los filtros muevan las cifras y se
puedan deshacer, y que subir un export distinto recalcule el tablero entero.
Son opcionales y se saltan solas si Playwright no está instalado:

```bash
pip install -r requirements-dev.txt && playwright install chromium
pytest ejercicio2_dashboard/tests/test_interfaz.py
```

</details>

---

<details>
<summary><b>Estructura del proyecto</b></summary>

<br>

```
prueba-tecnica-akila/
├── data/                    # los dos ficheros del enunciado
├── ejercicio1_triaje/       # pipeline de triaje + config editable + Excel generado
├── ejercicio2_dashboard/    # ETL, métricas y dashboard
├── docs/
│   ├── capturas/
│   ├── ejemplo-ejecucion/   # salida de referencia del triaje
│   ├── mutaciones.py        # arnés de pruebas de mutación
│   └── enunciado_original.md
├── requirements.txt         # 4 dependencias
└── requirements-ia.txt      # proveedores de IA (opcionales)
```

**Cuatro dependencias** en total: pandas, streamlit, openpyxl y pytest. Los
proveedores de IA son opcionales y no hacen falta para ejecutar nada. La
configuración del triaje usa `tomllib`, que ya viene con Python.

</details>

<details>
<summary><b>Seguridad</b></summary>

<br>

Las credenciales se leen **solo** de variables de entorno (`ANTHROPIC_API_KEY`,
`GEMINI_API_KEY`). No hay ninguna clave en el código, en la configuración ni en
el historial de este repositorio. `.gitignore` excluye `.env` desde el primer
commit.

Los datos de los correos son personales: el diseño los mantiene en local y solo
envía al proveedor de IA el texto necesario para clasificar, sin almacenarlo
fuera. En modo `reglas` no sale nada del equipo.

</details>
