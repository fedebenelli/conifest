---
title: Envolvente de Fases Interactiva
emoji: 🌡️
colorFrom: blue
colorTo: green
sdk: streamlit
sdk_version: 1.30.0
app_port: 8501
pinned: false
---

# Envolvente de fases interactiva (P-T)

Webapp didáctica que calcula y grafica la **envolvente de fases** de una mezcla
de 14 componentes (gases, CO₂, intermedios y pesados) usando
**Peng-Robinson 78** con regla de mezcla **QMR**, mediante la librería
[yaeos](https://pypi.org/project/yaeos/).

## Características

- **Sliders de grupo + sliders individuales**: ajusta la composición
- **Botón "Aplicar cambios"**: calcula la envolvente solo cuando se pulsa
  (sin cálculos intermedios al mover sliders)
- **Gráfica P-T** con ramas líquido/vapor y punto crítico
- **Gráfica de barras** de la composición por componente

## Ejecutar localmente

```bash
pip install -r requirements.txt
streamlit run app.py
# http://localhost:8501
```

## Despliegue en Render

```bash
# Build command:
pip install -r requirements.txt

# Start command:
streamlit run app.py --server.port $PORT --server.address 0.0.0.0
```

## Estructura

| Archivo | Descripción |
|---|---|
| `script.py` | Script original (referencia, incluye C50-C80A) |
| `envelope_model.py` | Modelo termodinámico + cálculo de la envolvente |
| `app.py` | App Streamlit |
| `requirements.txt` | Dependencias |
