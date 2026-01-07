import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { Search, RefreshCw, Sparkles, Filter, AlertCircle, AlertTriangle, Info, XCircle } from 'lucide-react';
import { logsApi, type LogEntry } from '../lib/api';
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

  const filteredLogs = logs?.filter((log: LogEntry) => {
    if (!searchQuery || useSemanticSearch) return true;
    return log.log.toLowerCase().includes(searchQuery.toLowerCase());
  });

  const getSeverityColor = (severity?: string) => {
    switch (severity?.toLowerCase()) {
      case 'error':
        return 'bg-red-50 text-red-700 border-red-200';
      case 'critical':
        return 'bg-rose-50 text-rose-700 border-rose-200';
      case 'warning':
        return 'bg-amber-50 text-amber-700 border-amber-200';
      case 'info':
        return 'bg-blue-50 text-blue-700 border-blue-200';
      default:
        return 'bg-slate-50 text-slate-700 border-slate-200';
    }
  };

  const getSeverityIcon = (severity?: string) => {
    switch (severity?.toLowerCase()) {
      case 'error':
      case 'critical':
        return <XCircle className="h-4 w-4" />;
      case 'warning':
        return <AlertTriangle className="h-4 w-4" />;
      case 'info':
        return <Info className="h-4 w-4" />;
      default:
        return <AlertCircle className="h-4 w-4" />;
    }
  };

  const severityCounts = filteredLogs?.reduce((acc: Record<string, number>, log) => {
    const severity = log.severity?.toLowerCase() || 'unknown';
    acc[severity] = (acc[severity] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  return (
    <div className="space-y-6">
      {/* Header & Stats */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h2 className="text-3xl font-bold text-slate-900">Log Viewer</h2>
          <p className="text-sm text-slate-500 mt-1">Real-time Kubernetes log monitoring</p>
        </div>
        <button
          onClick={() => refetch()}
          className="inline-flex items-center gap-2 px-4 py-2.5 bg-white border border-slate-200 rounded-lg shadow-sm text-sm font-semibold text-slate-700 hover:bg-slate-50 hover:border-slate-300 transition-all duration-200"
        >
          <RefreshCw className="h-4 w-4" />
          Refresh
        </button>
      </div>

      {/* Quick Stats */}
      {filteredLogs && filteredLogs.length > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-white rounded-xl p-4 border border-slate-200 shadow-sm">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-medium text-slate-500 uppercase">Total Logs</p>
                <p className="text-2xl font-bold text-slate-900 mt-1">{filteredLogs.length}</p>
              </div>
              <div className="p-3 bg-slate-100 rounded-lg">
                <Filter className="h-5 w-5 text-slate-600" />
              </div>
            </div>
          </div>
          <div className="bg-white rounded-xl p-4 border border-red-200 shadow-sm">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-medium text-red-500 uppercase">Errors</p>
                <p className="text-2xl font-bold text-red-700 mt-1">
                  {(severityCounts?.error || 0) + (severityCounts?.critical || 0)}
                </p>
              </div>
              <div className="p-3 bg-red-100 rounded-lg">
                <XCircle className="h-5 w-5 text-red-600" />
              </div>
            </div>
          </div>
          <div className="bg-white rounded-xl p-4 border border-amber-200 shadow-sm">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-medium text-amber-500 uppercase">Warnings</p>
                <p className="text-2xl font-bold text-amber-700 mt-1">{severityCounts?.warning || 0}</p>
              </div>
              <div className="p-3 bg-amber-100 rounded-lg">
                <AlertTriangle className="h-5 w-5 text-amber-600" />
              </div>
            </div>
          </div>
          <div className="bg-white rounded-xl p-4 border border-blue-200 shadow-sm">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-medium text-blue-500 uppercase">Info</p>
                <p className="text-2xl font-bold text-blue-700 mt-1">{severityCounts?.info || 0}</p>
              </div>
              <div className="p-3 bg-blue-100 rounded-lg">
                <Info className="h-5 w-5 text-blue-600" />
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="bg-white/80 backdrop-blur-sm p-6 rounded-xl border border-slate-200 shadow-sm">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label htmlFor="namespace" className="block text-sm font-semibold text-slate-700 mb-2">
              Namespace
            </label>
            <input
              id="namespace"
              type="text"
              value={namespace}
              onChange={(e) => setNamespace(e.target.value)}
              placeholder="All namespaces"
              className="w-full px-4 py-2.5 rounded-lg border border-slate-200 bg-white shadow-sm focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 transition-all"
            />
          </div>
          <div>
            <label htmlFor="pod" className="block text-sm font-semibold text-slate-700 mb-2">
              Pod Name
            </label>
            <input
              id="pod"
              type="text"
              value={podName}
              onChange={(e) => setPodName(e.target.value)}
              placeholder="All pods"
              className="w-full px-4 py-2.5 rounded-lg border border-slate-200 bg-white shadow-sm focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 transition-all"
            />
          </div>
          <div>
            <label htmlFor="search" className="block text-sm font-semibold text-slate-700 mb-2">
              Search Logs
            </label>
            <div className="relative">
              <input
                id="search"
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder={useSemanticSearch ? "AI semantic search..." : "Text search..."}
                className="w-full px-4 py-2.5 pl-10 rounded-lg border border-slate-200 bg-white shadow-sm focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 transition-all"
              />
              <Search className="absolute left-3 top-3 h-5 w-5 text-slate-400" />
            </div>
          </div>
        </div>
        <div className="mt-5 flex items-center gap-3 p-3 bg-gradient-to-r from-blue-50 to-indigo-50 rounded-lg border border-blue-200">
          <input
            id="semantic-search"
            type="checkbox"
            checked={useSemanticSearch}
            onChange={(e) => setUseSemanticSearch(e.target.checked)}
            className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-slate-300 rounded transition-all"
          />
          <label htmlFor="semantic-search" className="flex items-center gap-2 text-sm font-medium text-slate-700 cursor-pointer">
            <Sparkles className="h-4 w-4 text-blue-600" />
            Use AI semantic search (understands meaning, not just keywords)
          </label>
        </div>
      </div>

      {/* Logs List */}
      <div className="bg-white/80 backdrop-blur-sm rounded-xl border border-slate-200 shadow-lg overflow-hidden">
        {isLoading ? (
          <div className="p-12 text-center">
            <RefreshCw className="h-8 w-8 text-blue-500 animate-spin mx-auto mb-3" />
            <p className="text-slate-600 font-medium">Loading logs...</p>
          </div>
        ) : error ? (
          <div className="p-12 text-center">
            <AlertCircle className="h-8 w-8 text-red-500 mx-auto mb-3" />
            <p className="text-red-600 font-medium">
              Error loading logs: {error instanceof Error ? error.message : 'Unknown error'}
            </p>
          </div>
        ) : !filteredLogs || filteredLogs.length === 0 ? (
          <div className="p-12 text-center">
            <Search className="h-8 w-8 text-slate-400 mx-auto mb-3" />
            <p className="text-slate-500 font-medium">No logs found</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200">
              <thead>
                <tr className="bg-gradient-to-r from-slate-50 to-slate-100">
                  <th className="px-6 py-4 text-left text-xs font-bold text-slate-600 uppercase tracking-wider">
                    Timestamp
                  </th>
                  <th className="px-6 py-4 text-left text-xs font-bold text-slate-600 uppercase tracking-wider">
                    Namespace
                  </th>
                  <th className="px-6 py-4 text-left text-xs font-bold text-slate-600 uppercase tracking-wider">
                    Pod
                  </th>
                  <th className="px-6 py-4 text-left text-xs font-bold text-slate-600 uppercase tracking-wider">
                    Container
                  </th>
                  <th className="px-6 py-4 text-left text-xs font-bold text-slate-600 uppercase tracking-wider">
                    Severity
                  </th>
                  <th className="px-6 py-4 text-left text-xs font-bold text-slate-600 uppercase tracking-wider">
                    Message
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-slate-100">
                {filteredLogs.map((log, index) => (
                  <tr
                    key={log.id}
                    className="hover:bg-slate-50 transition-colors duration-150"
                    style={{ animationDelay: `${index * 20}ms` }}
                  >
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-slate-500">
                      {format(new Date(log.timestamp), 'MM/dd HH:mm:ss')}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-semibold text-slate-700">
                      {log.namespace}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-semibold text-slate-700">
                      {log.pod_name}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-600">
                      {log.container_name}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      {log.severity && (
                        <span className={`inline-flex items-center gap-1.5 px-3 py-1 text-xs font-bold rounded-full border ${getSeverityColor(log.severity)}`}>
                          {getSeverityIcon(log.severity)}
                          {log.severity}
                        </span>
                      )}
                    </td>
                    <td className="px-6 py-4 text-sm text-slate-700 font-mono max-w-2xl truncate">
                      {log.log}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
