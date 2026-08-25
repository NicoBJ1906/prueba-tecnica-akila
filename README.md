# Prueba técnica Akila · IA y optimización de procesos

Solución a los dos ejercicios de la prueba, por **Nicolás Bejarano**.

| | |
|---|---|
| **Ejercicio 1** · [Triaje de correos](ejercicio1_triaje/) | Un proceso de 2 h diarias reducido a 10–15 min de revisión, con IA solo donde aporta |
| **Ejercicio 2** · [Dashboard de ventas](ejercicio2_dashboard/) | Tablero para dirección, sobre datos que resultaron no estar limpios |

---

## Puesta en marcha

Requiere **Python 3.11 o superior**. Desde la raíz del repositorio:

**macOS / Linux**

```bash
git clone <url-del-repositorio>
cd prueba-tecnica-akila
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**Windows (PowerShell)**

```powershell
git clone <url-del-repositorio>
cd prueba-tecnica-akila
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Ejercicio 1 — triaje de correos

```bash
cd ejercicio1_triaje
python -m triaje
```

Genera `salida/seguimiento.xlsx` y `salida/informe_ejecucion.md`.
**No necesita ninguna clave de API**: sin credenciales clasifica con reglas
deterministas y produce el mismo Excel.

### Ejercicio 2 — dashboard

```bash
streamlit run ejercicio2_dashboard/dashboard/app.py
```

Se abre en `http://localhost:8501`.

### Pruebas

```bash
pytest
```

144 pruebas: unitarias, de integración, *golden tests* contra cifras verificadas
a mano y adversariales (intentos de manipulación del clasificador, respuestas
inválidas del modelo, caída del proveedor, entradas malformadas).

---

## Las dos decisiones que definen esta entrega

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

El export dice traer 457 apartamentos. **Son 300.** 109 unidades aparecen
repetidas con tipo, área, precio y estado contradictorios; 47 figuran vendidas
más de una vez en fechas distintas.

| | Leyendo el fichero tal cual | Consolidado |
|---|---|---|
| Vendidos | 271 | **209** |
| Disponibles | 186 | **91** |

Reportar «271 vendidos» a dirección sería inventar un 30 % de ventas. El
dashboard enseña el problema arriba del todo, documenta la regla que aplica y
permite comparar ambas lecturas con un selector, porque la regla es discutible y
quien decide debe poder verla.

El detalle, con las alternativas descartadas, está en el
[README del Ejercicio 2](ejercicio2_dashboard/README.md#lo-primero-que-hay-que-saber-sobre-estos-datos).

---

## Estructura

```
prueba-tecnica-akila/
├── data/                    # los dos ficheros del enunciado
├── ejercicio1_triaje/       # pipeline de triaje + config editable + Excel generado
├── ejercicio2_dashboard/    # ETL, métricas y dashboard
├── docs/
│   ├── presentacion.md      # guion de la presentación
│   ├── capturas/
│   └── enunciado_original.md
├── requirements.txt         # 4 dependencias
└── requirements-ia.txt      # proveedores de IA (opcionales)
```

**Cuatro dependencias** en total: pandas, streamlit, openpyxl y pytest. Los
proveedores de IA son opcionales y no hacen falta para ejecutar nada. La
configuración del triaje usa `tomllib`, que ya viene con Python.

## Seguridad

Las credenciales se leen **solo** de variables de entorno (`ANTHROPIC_API_KEY`,
`GEMINI_API_KEY`). No hay ninguna clave en el código, en la configuración ni en
el historial de este repositorio. `.gitignore` excluye `.env` desde el primer
commit.

Los datos de los correos son personales: el diseño los mantiene en local y solo
envía al proveedor de IA el texto necesario para clasificar, sin almacenarlo
fuera. En modo `reglas` no sale nada del equipo.
