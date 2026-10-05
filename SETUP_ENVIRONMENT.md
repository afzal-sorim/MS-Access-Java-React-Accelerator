# Environment & Project Setup Configuration

## 1. Operating System & Requirements
- **OS Level**: Windows (Required for Microsoft Access COM Automation `win32com`)
- **Node.js**: `v24.0.0` or higher (LTS: 24, tested on `24.16.0`)
- **Python**: `v3.11.9`
- **Java**: `17` (Minimum) / `25` (Recommended/Tested: `25.0.3`)
- **Maven**: `3.6.3` (Minimum) / `3.9.16` (Tested)

## 2. Microsoft Access Setup
- **Extraction Method**: MS Access COM automation (`Access.Application`) + DAO (`DAO.DBEngine.120`) + `SaveAsText` source export
- **Tested Version**: 14.0 (Access 2010)

## 3. Converter Wizard Backend (Python)
- **Framework**: FastAPI (>=0.115) with Uvicorn (>=0.30)
- **Database (Jobs & Cache)**: SQLite (`aiosqlite`)
- **Database (Authentication)**: MongoDB
- **Key Dependencies**: `sqlalchemy`, `pydantic`, `jinja2`, `pywin32`

## 4. Target/Generated Architecture
### Backend (Java/Spring Boot)
- **Framework**: Spring Boot `v4.1.0`
- **Managed by**: `spring-boot-starter-parent` BOM
- **Database Engine**: PostgreSQL `v18` (`postgres:18-alpine` Docker Image recommended)

### Frontend (React/Vite)
- **Library**: React `v19.2.8`
- **DOM / Routing**: React DOM `v19.2.8`, React Router DOM `v7.18.2`
- **Build Tool**: Vite `v8.2.1` with `@vitejs/plugin-react v6.0.5`
- **Additional Tools**: `lucide-react`, `recharts`, `quick-erd`

## 5. LLM Setup (Ollama)
The wizard uses an LLM to assist with Access-to-Java translation logic.
- **Provider**: OLLAMA
- **Model**: `deepseek-r1:1.5b`
- **Base URL**: `http://localhost:11434`
- **API Key**: Not required

### Ollama Setup Instructions
1. Download and install Ollama from [ollama.com](https://ollama.com/).
2. Open a terminal/command prompt and run:
   ```bash
   ollama run deepseek-r1:1.5b
   ```
3. Ensure the Ollama service is running on port `11434` before running the converter wizard.
