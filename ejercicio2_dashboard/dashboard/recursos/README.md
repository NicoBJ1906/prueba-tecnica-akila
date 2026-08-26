# Recursos gráficos

| Fichero | Uso |
|---|---|
| `akila-logo.png` | Original, tal cual se recibió: texto blanco sobre `#383838` |
| `akila-logo-oscuro.png` | **El que usa el dashboard.** Derivado del anterior |

El dashboard tiene la barra lateral en blanco, y sobre fondo claro el logo
original obligaba a pintar una banda oscura que pesaba más que los propios
datos. La versión en uso invierte esa relación: el texto en el gris de marca y
el fondo transparente.

Se generó a partir del original usando su **luminancia como máscara de
opacidad** —lo claro (el texto) queda opaco, el fondo oscuro se vuelve
transparente—, tiñendo después el resultado de `#383838` y recortándolo a su
contenido real, porque el PNG traía margen dentro de la caja:

```python
from PIL import Image

im = Image.open("akila-logo.png").convert("RGBA")
FONDO, TEXTO = 56, 255
alfa = im.convert("L").point(
    lambda v: max(0, min(255, round((v - FONDO) * 255 / (TEXTO - FONDO))))
)
teñido = Image.new("RGBA", im.size, (56, 56, 56, 255))
teñido.putalpha(alfa)
teñido.crop(alfa.getbbox()).save("akila-logo-oscuro.png")
```

El original se conserva porque es la fuente: si hiciera falta otra variante
—para fondo oscuro, o en otro tamaño—, se parte de él y no de una copia ya
procesada.
