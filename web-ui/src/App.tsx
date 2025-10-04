import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useState } from 'react';
import { Layout } from './components/Layout';
import { LogsViewer } from './components/LogsViewer';
import { AnalysisDashboard } from './components/AnalysisDashboard';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

type View = 'logs' | 'analyses';

function App() {
  const [currentView, setCurrentView] = useState<View>('logs');

  return (
    <QueryClientProvider client={queryClient}>
      <Layout currentView={currentView} onViewChange={setCurrentView}>
        {currentView === 'logs' && <LogsViewer />}
        {currentView === 'analyses' && <AnalysisDashboard />}
      </Layout>
    </QueryClientProvider>
  );
}

export default App;
