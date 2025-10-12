# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is the React + TypeScript frontend for the Timberline AI-powered log analysis platform. The web UI provides a modern interface for viewing Kubernetes logs, performing semantic searches, and visualizing AI-generated analysis results.

## Development Commands

```bash
# Install dependencies
npm install

# Start development server (runs on http://localhost:5173)
npm run dev

# Type-check and build for production
npm run build

# Preview production build locally
npm run preview

# Lint code
npm run lint
```

## Docker Deployment

```bash
# Build production Docker image (multi-stage build with nginx)
docker build -t timberline-web-ui .

# Run container
docker run -p 80:80 timberline-web-ui
```

The production build uses nginx with API proxying configured to avoid CORS issues. See nginx.conf:25-35 for the `/api/` proxy configuration that forwards to the `ai-analyzer` backend service.

## Architecture

### Tech Stack
- **React 19** with TypeScript for UI components
- **Vite** for development server and production builds
- **TanStack Query** for server state management and caching
- **Tailwind CSS 4** (PostCSS plugin) for styling
- **Axios** for HTTP requests
- **Lucide React** for icons

### State Management Pattern
The application uses TanStack Query (React Query) for all server state management:
- Query configuration is centralized in App.tsx:7-14 with shared defaults
- No manual refetch on window focus (`refetchOnWindowFocus: false`)
- Single retry attempt on failed requests
- API methods are organized in src/lib/api.ts with dedicated namespaces (`logsApi`, `analysisApi`)

### Routing Architecture
Currently uses simple state-based view switching (App.tsx:16-19):
- Two main views: `'logs'` and `'analyses'`
- View state managed in App component and passed to Layout
- Layout component (src/components/Layout.tsx) handles navigation UI
- No router library currently used (TanStack Router is installed but not yet implemented)

## API Integration

The frontend communicates with the backend via REST API. Base URL configuration:
- **Development**: Set via `VITE_API_URL` in `.env` (default: `http://localhost:8000`)
- **Production**: Uses relative URLs (empty string) so nginx proxy handles routing

### API Client Structure (src/lib/api.ts)
All API methods are organized into namespaced objects:

**logsApi**:
- `getLogs()` - Fetch logs with optional filters (namespace, pod_name, time range, limit)
- `searchLogs()` - Semantic search using AI embeddings

**analysisApi**:
- `getAnalyses()` - List all analyses
- `getAnalysis(id)` - Get specific analysis with cluster details
- `createAnalysis()` - Trigger new analysis with parameters (namespace, time_range_hours, min_cluster_size)
- `deleteAnalysis(id)` - Delete analysis

### TypeScript Types
All API types are defined in src/lib/api.ts:14-50:
- `LogEntry` - Individual log record with Kubernetes metadata
- `Analysis` - Analysis job with status, clusters, and severity scoring
- `ClusterInfo` - Grouped similar logs with labels and samples
- `CreateAnalysisRequest` - Parameters for triggering new analysis

## Component Architecture

### Main Components
- **App.tsx** - Root component with QueryClientProvider and view state
- **Layout.tsx** - Navigation header, view switcher, and main content wrapper
- **LogsViewer.tsx** - Log browsing, filtering, and semantic search interface
- **AnalysisDashboard.tsx** - List view of all analysis jobs
- **AnalysisDetails.tsx** - Detailed view of individual analysis with cluster visualization
- **CreateAnalysisModal.tsx** - Modal form for triggering new analyses

### Styling Patterns
- Tailwind CSS utility classes throughout
- Custom gradient effects and backdrop blur for modern UI
- Responsive design using Tailwind breakpoints (sm:, lg:)
- Custom animations defined via Tailwind (pulse effects, fading, sliding)
- Glass morphism effects with `backdrop-blur-md` and semi-transparent backgrounds

## Environment Configuration

Copy `.env.example` to `.env` before development:
```bash
cp .env.example .env
```

**Available variables**:
- `VITE_API_URL` - Backend API base URL (default: `http://localhost:8000`)

## Production Deployment

The multi-stage Dockerfile (Dockerfile:1-29):
1. **Build stage**: Node 20 Alpine, installs deps, runs `npm run build`
2. **Production stage**: Nginx Alpine, copies built assets to `/usr/share/nginx/html`

Nginx configuration (nginx.conf) includes:
- SPA fallback routing (all routes serve index.html)
- Static asset caching (1 year for images, fonts, CSS, JS)
- Gzip compression
- API proxy to backend at `http://ai-analyzer:8000`

## Notes

- No test suite currently implemented (no .test.tsx or .spec.tsx files in src/)
- ESLint configured with TypeScript, React hooks, and React Refresh rules
- TypeScript strict mode enabled via tsconfig.json
- Hot Module Replacement (HMR) enabled in development via Vite
