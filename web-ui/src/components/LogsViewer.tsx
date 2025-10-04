import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { Search, RefreshCw } from 'lucide-react';
import { logsApi } from '../lib/api';
import { format } from 'date-fns';

export function LogsViewer() {
  const [searchQuery, setSearchQuery] = useState('');
  const [namespace, setNamespace] = useState('');
  const [podName, setPodName] = useState('');
  const [useSemanticSearch, setUseSemanticSearch] = useState(false);

  const { data: logs, isLoading, error, refetch } = useQuery({
    queryKey: ['logs', namespace, podName, searchQuery, useSemanticSearch],
    queryFn: async () => {
      if (useSemanticSearch && searchQuery) {
        return logsApi.searchLogs(searchQuery, 100);
      }
      return logsApi.getLogs({
        namespace: namespace || undefined,
        pod_name: podName || undefined,
        limit: 100,
      });
    },
  });

  const filteredLogs = logs?.filter(log => {
    if (!searchQuery || useSemanticSearch) return true;
    return log.log.toLowerCase().includes(searchQuery.toLowerCase());
  });

  const getSeverityColor = (severity?: string) => {
    switch (severity?.toLowerCase()) {
      case 'error':
      case 'critical':
        return 'text-red-600 bg-red-50';
      case 'warning':
        return 'text-yellow-600 bg-yellow-50';
      case 'info':
        return 'text-blue-600 bg-blue-50';
      default:
        return 'text-gray-600 bg-gray-50';
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <h2 className="text-2xl font-bold text-gray-900">Log Viewer</h2>
        <button
          onClick={() => refetch()}
          className="inline-flex items-center px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
        >
          <RefreshCw className="h-4 w-4 mr-2" />
          Refresh
        </button>
      </div>

      {/* Filters */}
      <div className="bg-white p-4 rounded-lg shadow">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label htmlFor="namespace" className="block text-sm font-medium text-gray-700 mb-1">
              Namespace
            </label>
            <input
              id="namespace"
              type="text"
              value={namespace}
              onChange={(e) => setNamespace(e.target.value)}
              placeholder="All namespaces"
              className="w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
            />
          </div>
          <div>
            <label htmlFor="pod" className="block text-sm font-medium text-gray-700 mb-1">
              Pod Name
            </label>
            <input
              id="pod"
              type="text"
              value={podName}
              onChange={(e) => setPodName(e.target.value)}
              placeholder="All pods"
              className="w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
            />
          </div>
          <div>
            <label htmlFor="search" className="block text-sm font-medium text-gray-700 mb-1">
              Search Logs
            </label>
            <div className="relative">
              <input
                id="search"
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder={useSemanticSearch ? "Semantic search..." : "Text search..."}
                className="w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 pr-10"
              />
              <Search className="absolute right-3 top-2.5 h-5 w-5 text-gray-400" />
            </div>
          </div>
        </div>
        <div className="mt-4 flex items-center">
          <input
            id="semantic-search"
            type="checkbox"
            checked={useSemanticSearch}
            onChange={(e) => setUseSemanticSearch(e.target.checked)}
            className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
          />
          <label htmlFor="semantic-search" className="ml-2 block text-sm text-gray-700">
            Use AI semantic search (understands meaning, not just keywords)
          </label>
        </div>
      </div>

      {/* Logs List */}
      <div className="bg-white rounded-lg shadow overflow-hidden">
        {isLoading ? (
          <div className="p-8 text-center text-gray-500">Loading logs...</div>
        ) : error ? (
          <div className="p-8 text-center text-red-600">
            Error loading logs: {error instanceof Error ? error.message : 'Unknown error'}
          </div>
        ) : !filteredLogs || filteredLogs.length === 0 ? (
          <div className="p-8 text-center text-gray-500">No logs found</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Timestamp
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Namespace
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Pod
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Container
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Severity
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Message
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {filteredLogs.map((log) => (
                  <tr key={log.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {format(new Date(log.timestamp), 'MM/dd HH:mm:ss')}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {log.namespace}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {log.pod_name}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {log.container_name}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      {log.severity && (
                        <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${getSeverityColor(log.severity)}`}>
                          {log.severity}
                        </span>
                      )}
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-900 max-w-2xl truncate">
                      {log.log}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Stats */}
      {filteredLogs && filteredLogs.length > 0 && (
        <div className="text-sm text-gray-500 text-right">
          Showing {filteredLogs.length} log{filteredLogs.length !== 1 ? 's' : ''}
        </div>
      )}
    </div>
  );
}
