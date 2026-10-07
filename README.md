---
title: Envolvente de Fases Interactiva
emoji: 🌡️
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
pinned: false
---

# Envolvente de fases interactiva (P-T)

Webapp didáctica que calcula y grafica la **envolvente de fases** de una mezcla
de 14 componentes (gases, CO₂, intermedios y pesados) usando
**Peng-Robinson 78** con regla de mezcla **QMR**, mediante la librería
[yaeos](https://pypi.org/project/yaeos/).

La composición por defecto es la del `script.py` de este repositorio (sin el
último componente, C50-C80A); muévela con los sliders y observa en tiempo real
(~50 ms) cómo cambia la envolvente P vs T.

## Características

- **Sliders de grupo + sliders individuales**: el slider maestro de cada grupo
  (Gases, CO₂, Intermedios, Pesados) fija su participación en la mezcla y
  reescala los componentes; los sliders individuales ajustan la distribución
  interna.
- **C50-C80A (asfaltenos) fuera del modelo**: el último componente del script
  se eliminó por completo; no aparece en `z`, `tc/pc/w` ni en `kij`.
- **Gráfica P-T** con ramas líquido/vapor coloreadas y punto crítico marcado.
- **Gráfica de barras** de la composición actual por componente (coloreada por
  grupo) con la composición por defecto como referencia.
- Manejo de errores: composiciones extremas muestran un aviso en lugar de
  romper la app.
- **Responsive**: usable en smartphone (gráfica primero, grupos en acordeones
  plegados) y en computadora (sidebar + gráfica).

## Ejecutar localmente

```bash
pip install -r requirements.txt
python app.py
# http://localhost:8050
```

## Despliegue en Hugging Face Spaces

Este README incluye el front-matter (`sdk: docker`) que define el Space.
El `Dockerfile` expone el puerto **7860**. Publicar:

```bash
huggingface-cli login
huggingface-cli upload <usuario>/envolvente-fases . . --repo-type=space
```

> **Requisito**: `yaeos==4.5.4` debe estar publicado en PyPI. Las ruedas de
> 4.5.3 traían `PT_GNU_STACK RWE` (stack ejecutable), que kernels ≥ 6.13
> rechazan al cargar el `.so`; 4.5.4 se publica con `-Wl,-z,noexecstack`.
> Verificar antes de construir la imagen:
> `pip download yaeos==4.5.4 --only-binary=:all: -d /tmp/y` y comprobar
> `readelf -lW .../yaeos/lib/*.so | grep GNU_STACK` → debe dar `RW`.

## Estructura

| Archivo | Descripción |
|---|---|
| `script.py` | Script original (referencia, incluye C50-C80A) |
| `envelope_model.py` | Modelo termodinámico + cálculo de la envolvente (caché y errores) |
| `app.py` | Layout Dash y callbacks |
| `requirements.txt` | Dependencias |
| `Dockerfile` | Contenedor para HF Spaces |

## Verificación

- `kij` (14×14, simétrica), `z` normalizada y las envolventes se verificaron
  contra `script.py` antes de eliminar C50-C80A; con el componente fuera del
  modelo la envolvente por defecto da 285 puntos, T 199.2–784.8 K,
  P 1–269.5 bar (punto crítico sin cambios: 643.6 K / 223.3 bar).
- Cada cálculo toma ~60 ms (cacheado: instantáneo).
