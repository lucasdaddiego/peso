# Metodología

`peso` convierte una cantidad de pesos de cualquier mes desde **enero de 1993** a pesos de hoy,
usando un **índice de precios al consumidor empalmado** a partir de series oficiales, y muestra el
valor en dólares al tipo de cambio oficial y al informal ("blue").

## El índice de precios (IPC empalmado)

El IPC del INDEC fue **intervenido entre 2007 y 2015**: la inflación oficial de esos años quedó
muy por debajo de la real. Un convertidor que usara esos números subestimaría gravemente cuánto
valían los pesos viejos. Por eso el índice se construye en tres tramos y se empalma:

| Período | Fuente | Por qué |
|---|---|---|
| 1993-01 … 2006-12 | **INDEC, IPC-GBA** (base abril 2008) | Serie oficial confiable, anterior a la intervención. |
| 2007-01 … 2016-11 | **IPC San Luis** | Dirección provincial fuera de la intervención; referencia creíble de la "inflación verdadera". |
| 2016-12 … *vintage* | **INDEC, IPC Nacional** (base dic-2016) | Serie oficial nacional, posterior a la normalización del INDEC. |

**Cómo se empalma.** Cada tramo aporta su **variación mensual** (no su nivel: las bases son
distintas). El nivel de cada mes es el del mes anterior multiplicado por la variación del tramo que
"posee" ese mes. Como cada fuente cubre el mes *anterior* al inicio de su ventana, el cambio de
tramo es un **solapamiento limpio de un mes**, sin huecos ni dobles conteos:

- IPC-GBA posee 1993-02 … 2006-12 (tiene 1993-01).
- San Luis posee 2007-01 … 2016-12 (tiene 2006-12, así que el empalme de 2007-01 es limpio; y
  aporta el paso de 2016-11 → 2016-12, el mes base de la serie nacional).
- IPC Nacional posee 2017-01 … *vintage* (tiene 2016-12, su base = 100).

Finalmente, todo el índice se **rebasa para que el mes más reciente valga 100**, de modo que se lee
directamente en "pesos de hoy". El equivalente de hoy de `X` pesos del mes `m` es
`X × 100 / IPC[m]`.

> Para el período intervenido se eligió **San Luis** como una alternativa creíble entre varias
> (IPC Congreso, IPC CABA, otras provincias), todas con valores parecidos. Su uso aquí es una
> decisión metodológica explícita, no la única posible.

## El dólar

- **Oficial:** tipo de cambio de referencia del **BCRA** (dólar billete), diario desde 1992 (vía
  datos.gob.ar). Durante la convertibilidad (1992–2001) ronda 1,00 peso por dólar.
- **Blue (informal):** cotización histórica de **Bluelytics**, diaria desde 2011. Antes del cepo
  cambiario (fines de 2011) no había un mercado paralelo relevante, así que para esos meses el blue
  se toma **igual al oficial** (y se marca como estimado).
- Ambas series se llevan a frecuencia mensual tomando el valor de fin de mes.

## Vintage / reproducibilidad

Todas las series se **truncan al mes `DATA_VINTAGE`** (`pipeline/config.py`). Así el cálculo es
reproducible sin importar cuándo se ejecute: los meses nuevos que publiquen las fuentes se ignoran
hasta que se actualice el vintage. Para actualizar: subir `DATA_VINTAGE` al último mes completo,
correr `make data` y commitear el artefacto regenerado.

## Validación

El pipeline reproduce, dentro de tolerancia, cifras conocidas (o falla el build):

- **IPC Nacional (INDEC), inflación interanual dic–dic 2017–2024:** 24,8 · 47,6 · 53,8 · 36,1 ·
  50,9 · 94,8 · 211,4 · 117,8 %.
- **IPC San Luis dic–dic 2007–2015** (la década intervenida): ~21–39 %/año — muy por encima del
  ~10 % que declaraba el INDEC oficial de esos años.
- **IPC-GBA 2002** (colapso de la convertibilidad): 40,9 %.
- **Tipo de cambio en convertibilidad:** ≈ 1,00 peso/dólar a lo largo de 1992–2001.
- **Cross-check acumulado independiente:** $1.000 de enero-2003 ≈ pesos de la vintage.

## Límites

- Es **inflación nacional**: el costo de vida real de cada persona depende de su canasta y su región.
- El **nivel** de los pesos más viejos tiene más incertidumbre (empalme de canastas con bases
  distintas); las **variaciones** recientes son más firmes.
- El **blue** arranca en 2011 y es ruidoso; antes se usa el oficial.
- Convierte **poder de compra**, no rendimientos: no contempla intereses ni inversiones.

> Elaboración propia en base a series oficiales del INDEC (IPC) y del BCRA (tipo de cambio), vía
> datos.gob.ar, empalmadas con el IPC de San Luis para el período de intervención del INDEC
> (2007–2015), y cotización informal histórica de Bluelytics.
