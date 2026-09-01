# MS Access Converter Wizard - Frontend

React + Vite frontend for the MS Access → Spring Boot + React + PostgreSQL Converter wizard.

## Features

Implements the 6-step wizard per specification section 47:

1. **Select Access Application** - Drag/drop or browse for .accdb/.mdb files
2. **Analyze Application** - Real-time scanning of tables, queries, forms, reports, VBA, macros, dependencies
3. **Conversion Configuration** - Configure Spring Boot, React, PostgreSQL versions, auth, reports, migration strategy
4. **Map & Review** - Tabbed review of all objects with status, risk, confidence, and manual mapping
5. **Generate Project** - Real-time progress of database, backend, frontend generation, building, testing, repair
6. **Summary** - Coverage metrics, build/test status, unsupported objects, warnings, download actions

## Development

```bash
# Install dependencies
npm install

# Start development server (proxies API to localhost:8080)
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```

## Integration

The frontend communicates with the FastAPI backend at `http://localhost:8000` via:
- REST API (`/api/jobs`, `/api/versions`, etc.)
- WebSocket (`/ws/jobs/{job_id}`) for real-time progress

## Project Structure

```
src/
├── components/
│   ├── WizardApp.jsx          # Main app with routing
│   └── wizard/
│       ├── WizardContainer.jsx # Stepper navigation + step rendering
│       └── steps/             # Individual step components
│           ├── Step1SelectApplication.jsx
│           ├── Step2Analyze.jsx
│           ├── Step3Configure.jsx
│           ├── Step4Review.jsx
│           ├── Step5Generate.jsx
│           └── Step6Summary.jsx
├── context/
│   └── WizardContext.jsx      # Global wizard state management
├── services/
│   └── api.js                 # Backend API client
├── utils/
│   ├── constants.js           # Wizard constants and status enums
│   └── helpers.js             # Utility functions
└── styles/
    └── index.css              # Global styles with CSS variables
```

## Configuration

The wizard reads available technology versions from the backend `/api/versions` endpoint and uses them to populate dropdowns. Defaults are defined in `WizardContext.jsx` initial state.

## Status Model

Object statuses follow spec section 48:
- DISCOVERED, ANALYZING, SUPPORTED, SUPPORTED_WITH_REVIEW, CONVERTING, CONVERTED
- BUILD_ERROR, AUTO_REPAIRED, VALIDATED, UNSUPPORTED, FAILED

Supportability statuses follow spec section 12:
- SUPPORTED, SUPPORTED_WITH_TRANSFORMATION, SUPPORTED_WITH_REVIEW, UNSUPPORTED, FAILED_EXTRACTION