# Guion de la presentación

Notas para defender la entrega. No es un documento para entregar: es para
llegar preparado.

---

## Apertura (30 segundos)

> «Los dos ejercicios tenían una trampa parecida, y creo que ahí está lo
> interesante. En el primero, la trampa es pensar que "automatizar con IA"
> significa que la IA lo haga todo. En el segundo, la trampa está en los datos:
> el fichero dice traer 457 apartamentos y en realidad son 300.»

Con esa frase quedan planteadas las dos ideas que se van a defender. Todo lo
demás es desarrollarlas.

---

## Ejercicio 1 · Demostración (4 minutos)

### Qué enseñar, en este orden

1. **El Excel generado.** Empezar por el resultado, no por el código. Abrir
   `docs/ejemplo-ejecucion/seguimiento.xlsx`:
   - Hoja **Resumen**: 15 correos → 15 filas, 12 automáticas, 2 a revisión.
   - Hoja **Seguimiento**: las seis columnas pedidas, en orden.
   - Hoja **Para revisar**: *«esta es la única hoja que la persona abre cada
     mañana. Dos filas, no cuarenta correos.»*
   - Hoja **Descartados**: *«y esta es la que hace que se pueda confiar en la
     anterior: aquí está lo que el sistema decidió no procesar, y por qué.»*

2. **Ejecutarlo en vivo.** `python -m triaje` — tarda menos de un segundo.
   Ejecutarlo **dos veces seguidas**: la segunda no escribe nada.
   > «El enunciado decía que a veces se duplica una entrada. Aquí no puede
   > pasar, aunque alguien lance el proceso tres veces.»

3. **Abrir `config.toml`.** Es el argumento de adopción más fuerte.
   > «Esto lo mantiene la persona del proceso, no yo. Si mañana Cartera pasa a
   > llamarse Tesorería, o si aparece un proveedor que satura la bandeja, lo
   > cambia aquí y guarda. No hay que tocar código ni volver a desplegar.»

### El punto que hay que dejar clarísimo

> «Solo una de las once etapas usa un modelo de lenguaje. Todo lo demás son
> reglas. Y eso no es porque no me fíe de la IA: es que extraer "apartamento
> 1105" con una expresión regular acierta el 100 % y cuesta cero. Pedírselo a un
> modelo sería pagar por una respuesta peor.»

Y el remate:

> «Lo que el sistema nunca hace es responderle al cliente. Esa fue la primera
> decisión que tomé. Las respuestas comprometen fechas de entrega y montos: una
> alucinación ahí no es un error de clasificación, es un problema con un cliente
> que ya pagó. El sistema deja la fila lista; el mensaje lo manda una persona.»

### Si preguntan «¿y por qué no usar IA para todo?»

Tres razones, en este orden:

1. **Coste de error asimétrico.** Automatizar bien un desistimiento ahorra dos
   minutos; automatizarlo mal cuesta un pleito. La asimetría decide.
2. **Trazabilidad.** Cuando un cliente reclame por qué su correo tardó tres
   días, hay que poder señalar la regla. «El modelo lo interpretó así» no es una
   respuesta que se le pueda dar a nadie.
3. **Consistencia.** La urgencia y el responsable son política de la empresa. Un
   modelo puede dar respuestas distintas al mismo caso en semanas distintas; una
   tabla, no.

### Si preguntan por el coste

> «Los 15 correos cuestan menos de un centavo con Haiku. A 50 correos diarios,
> son dos o tres dólares al mes; con Gemini Flash, cero. El coste nunca fue el
> problema de este proyecto. La confianza sí, y por eso el esfuerzo del diseño
> está en la trazabilidad, no en ahorrar tokens.»

### Si preguntan qué pasa si la IA falla

Enseñar el test: `pytest -k test_si_el_modelo_falla` .

> «Cae a reglas y marca esas filas para revisión. Ningún correo se pierde nunca.
> De hecho, el modo sin IA es el que ustedes acaban de ver funcionando: no hace
> falta ninguna clave de API para ejecutarlo.»

---

## Ejercicio 2 · Demostración (4 minutos)

### Qué enseñar

1. **Abrir el dashboard y no decir nada durante tres segundos.** Que lean el
   aviso amarillo de arriba.

   > «457 registros, 300 apartamentos reales.»

2. **Enseñar el ejemplo concreto.** `Torre 1 Apto 2003` aparece dos veces: una
   como Apartaestudio de 38 m² disponible, otra como 1 Alcoba de 57 m² vendida.
   Mismo apartamento físico, dos versiones incompatibles.

3. **Mover el selector a «Export crudo»** y dejar que vean los números cambiar
   de 209 a 271.

   > «Esta es la diferencia entre reportar el proyecto al 70 % o al 59 %. Si
   > presento la primera lectura sin decir nada, estoy inventando un 30 % de
   > ventas que no existen.»

4. **Volver a consolidado** y recorrer los cinco apartados pedidos, rápido.

5. **Cerrar con el dato de negocio**: ritmo de 5,1 apartamentos por semana,
   4 meses de inventario.

   > «Los cinco apartados eran lo que pedían. Esto es lo que yo le preguntaría a
   > continuación al tablero si dirigiera el proyecto.»

### Si preguntan por la regla de consolidación

No defenderla como si fuera la única posible — **eso es lo que la hace fuerte**:

> «Gana la venta más reciente porque una venta es un hecho fechado y con
> contraparte: es la evidencia más fuerte que hay en el fichero. Consideré
> quedarme con el último registro, pero eso borra ventas reales: daba 184
> vendidos. Y descartar las unidades en conflicto tiraba un tercio del proyecto.
> Puede que ustedes sepan algo del sistema de origen que cambie el criterio; por
> eso la regla está documentada y el selector deja ver las dos lecturas. Lo que
> no me parecía defendible era no decir nada.»

### El nexo entre los dos ejercicios (el remate)

Guardarlo para el final. Es lo que nadie más va a decir:

> «Una cosa que me llamó la atención: entre los correos hay uno de un cliente que
> desiste de la compra del apartamento 605 y pide la devolución. Y en el fichero
> de apartamentos hay 47 unidades que figuran vendidas más de una vez en fechas
> distintas.
>
> Si el sistema de origen registra cada operación como una fila nueva en lugar de
> actualizar la existente, una unidad vendida, desistida y revendida deja
> exactamente ese rastro. No lo puedo confirmar sin ver el sistema, pero si es
> así, el arreglo de fondo no está en el dashboard: está en el proceso que genera
> el export. El dashboard solo hace visible el síntoma.»

---

## «Necesito que ayudes a optimizar este proceso, ¿cómo lo harías?»

La pregunta que anuncian al final de los dos ejercicios. Un método, no una
lista de herramientas:

**1. Medir antes de tocar nada.** Cuántos correos entran, cuánto tarda cada
paso, dónde se pierde el tiempo de verdad. En este caso: la persona no tarda 2
horas decidiendo, tarda 2 horas transcribiendo. Esa distinción decide qué se
automatiza.

**2. Separar lo mecánico de lo que necesita criterio.** Lo mecánico —copiar
fechas, detectar duplicados, asignar el área que corresponde— es determinista y
se automatiza entero. Lo que requiere criterio se automatiza solo hasta el punto
en que el coste de equivocarse sea asumible.

**3. Empezar por lo que se puede revertir.** Escribir una fila en un Excel es
reversible; responderle a un cliente, no. Por eso el sistema empieza escribiendo
filas y las acciones sobre el buzón quedan para cuando el piloto demuestre que
la clasificación es fiable.

**4. Dejar que el proceso se explique solo.** Cada ejecución produce un informe:
qué entró, qué se descartó y por qué, cuánto quedó para revisión. Sin eso no hay
supervisión posible, y sin supervisión la automatización no se adopta: se
desconfía de ella y se acaba haciendo el trabajo dos veces.

**5. Dejar el control en manos de quien opera.** Los responsables, los filtros y
los umbrales viven en un fichero de texto que mantiene la empresa. Si cada
cambio necesita un desarrollador, el sistema envejece mal.

Y para reporting específicamente:

> «Lo mismo, con un añadido: la mitad del trabajo de un reporting no es el
> gráfico, es cuadrar los datos. Aquí el ETL está separado de la interfaz y
> testeado contra cifras verificadas a mano; el dashboard es la capa fina de
> encima. Cuando dirección pregunte "¿este número es correcto?", la respuesta
> está en un test, no en una hoja de cálculo que alguien revisó una vez.»

---

## Preguntas incómodas y respuestas honestas

| Pregunta | Respuesta |
|---|---|
| «¿Esto no es demasiado para 15 correos?» | «El código que resuelve 15 correos y el que resuelve 500 al día es el mismo. Lo que añadí sobre el mínimo es idempotencia, trazabilidad y configuración externa — y las tres solo tienen sentido si esto se va a usar de verdad todos los días.» |
| «¿Por qué Streamlit y no algo más potente?» | «Porque el problema es un tablero de lectura, no una aplicación web. Con Streamlit son cuatro dependencias y un comando, y funciona igual en Windows. Un frontend con build propio habría añadido horas y superficie de fallo sin mejorar lo que ustedes ven en pantalla.» |
| «¿Qué falta para producción?» | «Conectar el buzón real: es una función, `leer_correos()`. Y el piloto en paralelo de una o dos semanas, que no es opcional — hay que medir la concordancia con la persona antes de que deje de revisar todo.» |
| «¿Y si el clasificador se equivoca?» | «Se equivocará. Por eso hay una columna de confianza, un umbral configurable y una hoja de revisión. La pregunta correcta no es si se equivoca, es si los errores se detectan y cuánto cuestan. Los caros —desistimientos, devoluciones— ni siquiera llegan al modelo.» |
| «¿Probaste con IA de verdad o solo con reglas?» | Ser honesto: «El pipeline con IA está implementado y sus guardrails testeados con dobles. Lo que ven ejecutado es el modo reglas, que es el peor caso y aun así clasifica bien los 15. Puedo lanzarlo con una clave ahora mismo si quieren verlo.» |
| «¿Cuánto tiempo te llevó?» | La verdad. Y añadir dónde se fue el tiempo: en decidir qué **no** automatizar, no en escribir el código. |

---

## Cierre

> «Si me quedo con una sola cosa de esta prueba: la parte difícil no era hacer
> que la IA clasificara correos, eso funciona a la primera. La parte difícil era
> decidir dónde parar, y construir el sistema de forma que cuando se equivoque
> —que se va a equivocar— alguien lo note a tiempo.»
