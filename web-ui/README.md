# Timberline Web UI

React + TypeScript frontend for the Timberline log analysis platform.

## Features

- **Log Viewer**: Browse and filter Kubernetes logs with real-time updates
- **Semantic Search**: AI-powered log search that understands meaning, not just keywords
- **AI Analysis Dashboard**: View and manage log analysis results
- **Cluster Visualization**: See grouped similar logs with severity scoring
- **Analysis Triggering**: Create new AI analyses with custom parameters

## Tech Stack

- React 18 with TypeScript
- Vite for fast development and building
- TanStack Query for data fetching and caching
- Tailwind CSS for styling
- Lucide React for icons
- Axios for API communication

## Development

### Prerequisites

- Node.js 20+
- npm or yarn

### Setup

```bash
# Install dependencies
npm install

# Copy environment file
cp .env.example .env

# Start development server
npm run dev
```

The app will be available at http://localhost:5173

### Environment Variables

- `VITE_API_URL`: Backend API URL (default: http://localhost:8000)

## Building

```bash
# Build for production
npm run build

# Preview production build
npm run preview
```

## Docker

```bash
# Build Docker image
docker build -t timberline-web-ui .

# Run container
docker run -p 80:80 timberline-web-ui
```

The nginx configuration includes API proxying to avoid CORS issues in production.

## Project Structure

```
web-ui/
├── src/
│   ├── components/          # React components
│   │   ├── Layout.tsx       # Main layout with navigation
│   │   ├── LogsViewer.tsx   # Log viewing and filtering
│   │   ├── AnalysisDashboard.tsx
│   │   ├── CreateAnalysisModal.tsx
│   │   └── AnalysisDetails.tsx
│   ├── lib/
│   │   └── api.ts           # API client and types
│   ├── App.tsx              # Root component
│   └── main.tsx             # Entry point
├── Dockerfile               # Production container
├── nginx.conf               # Nginx configuration
└── tailwind.config.js       # Tailwind CSS config
```

## API Integration

The frontend expects the following backend API endpoints:

### Logs API
- `GET /api/v1/logs` - Fetch logs with optional filters
- `POST /api/v1/logs/search` - Semantic search

### Analysis API
- `GET /api/v1/analyses` - List all analyses
- `GET /api/v1/analyses/:id` - Get analysis details
- `POST /api/v1/analyses` - Create new analysis
- `DELETE /api/v1/analyses/:id` - Delete analysis
