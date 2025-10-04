import { Activity, FileText } from 'lucide-react';

interface LayoutProps {
  children: React.ReactNode;
  currentView: 'logs' | 'analyses';
  onViewChange: (view: 'logs' | 'analyses') => void;
}

export function Layout({ children, currentView, onViewChange }: LayoutProps) {
  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center py-4">
            <div className="flex items-center">
              <Activity className="h-8 w-8 text-blue-600" />
              <h1 className="ml-3 text-2xl font-bold text-gray-900">Timberline</h1>
              <span className="ml-3 text-sm text-gray-500">Log Analysis Platform</span>
            </div>
          </div>
        </div>
      </header>

      {/* Navigation */}
      <nav className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex space-x-8">
            <button
              onClick={() => onViewChange('logs')}
              className={`flex items-center px-3 py-4 text-sm font-medium border-b-2 transition-colors ${
                currentView === 'logs'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              <FileText className="h-5 w-5 mr-2" />
              Logs
            </button>
            <button
              onClick={() => onViewChange('analyses')}
              className={`flex items-center px-3 py-4 text-sm font-medium border-b-2 transition-colors ${
                currentView === 'analyses'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              <Activity className="h-5 w-5 mr-2" />
              AI Analysis
            </button>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {children}
      </main>
    </div>
  );
}
