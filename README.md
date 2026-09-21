# 🗺️ WebMapper — Herramienta de Mapeo de Aplicaciones Web

WebMapper es una aplicación web local para **mapear aplicaciones web** mediante spidering con profundidad configurable, fuzzing de contenido, identificación de formularios y visualización interactiva del grafo de la aplicación.

> ⚠️ **Uso ético**: Esta herramienta es para uso educativo y de auditoría autorizada. Solo escanea sitios para los que tengas autorización explícita.

## 🚀 Características

- **Spidering configurable**: Profundidad 0–3, límite de páginas, respeto de `robots.txt`, delay configurable
- **Fuzzing de contenido**: Diccionario personalizable (~200 rutas por defecto), extensiones configurables, control de concurrencia
- **Identificación de formularios**: Extracción de `<form>`, campos, tokens CSRF, clasificación automática (login, búsqueda, upload)
- **Grafo interactivo**: Visualización con Cytoscape.js — filtrado por tipo, cambio de layout, zoom, arrastre, tooltips
- **Árbol de rutas**: Representación jerárquica ASCII del sitemap
- **Tablas de resultados**: Búsqueda en tiempo real, ordenación por columna, badges de estado HTTP
- **Gráficos**: Distribución de códigos HTTP, tipos de formulario, recursos por dominio, profundidad
- **Exportación**: JSON, CSV (ZIP) e informe HTML autocontenido con grafo interactivo
- **Progreso en tiempo real**: Server-Sent Events (SSE) con log en vivo

## 📋 Requisitos

- **Python 3.10+**
- **pip** (gestor de paquetes de Python)

## 🔧 Instalación

```bash
# 1. Clonar o descargar el proyecto
cd ProyectoIntroduccionSeguridad

# 2. Crear entorno virtual (recomendado)
python3 -m venv venv
source venv/bin/activate   # macOS/Linux
# venv\Scripts\activate    # Windows

# 3. Instalar dependencias
pip install -r requirements.txt
```

## ▶️ Ejecución

```bash
python run.py
```

La aplicación se abre en **http://127.0.0.1:8000**

## 📖 Uso

1. **Introducir URL**: Escribe la URL objetivo (incluir `http://` o `https://`)
2. **Configurar parámetros**: Profundidad (0–3), máximo de páginas, delay entre peticiones
3. **Opciones de fuzzing**: Activar fuzzing, configurar extensiones y concurrencia, subir diccionario personalizado
4. **Confirmar autorización**: Marcar la casilla de autorización
5. **Iniciar escaneo**: El progreso se muestra en tiempo real via SSE
6. **Explorar resultados**: Grafo interactivo, tablas con búsqueda, gráficos de distribución
7. **Exportar**: Descargar resultados en JSON, CSV o informe HTML

## 🏗️ Arquitectura

```
├── backend/
│   ├── app.py              # FastAPI + endpoints + SSE
│   ├── spider.py           # Motor de spidering async
│   ├── fuzzer.py           # Motor de fuzzing async
│   ├── form_extractor.py   # Extracción de formularios
│   ├── graph_builder.py    # Construcción del grafo
│   ├── exporter.py         # Exportación JSON/CSV/HTML
│   └── models.py           # Modelos Pydantic
├── frontend/
│   ├── index.html          # SPA principal
│   ├── css/style.css       # Estilos dark mode
│   └── js/                 # Módulos JS
├── wordlists/
│   └── common.txt          # Diccionario por defecto
├── requirements.txt
├── run.py                  # Entry point
└── README.md
```

## 🛡️ Seguridad y Ética

- **Rate limiting por defecto**: Delay mínimo de 1 segundo entre peticiones
- **Límite de páginas**: Máximo 50 páginas por defecto
- **Respeto de robots.txt**: Se consulta y respeta automáticamente
- **User-Agent identificable**: `WebMapper/1.0 (Educational Security Tool)`
- **Confirmación de autorización**: Obligatoria antes de iniciar cualquier escaneo

## 📦 Dependencias

| Paquete | Uso |
|---------|-----|
| FastAPI | Framework web async |
| uvicorn | Servidor ASGI |
| httpx | Cliente HTTP async |
| beautifulsoup4 | Parsing HTML |
| lxml | Parser rápido para BS4 |
| pydantic | Modelos de datos |
| python-multipart | Upload de archivos |

## 📄 Licencia

Proyecto educativo — Universidad
