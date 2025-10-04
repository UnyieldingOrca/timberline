import { X, AlertTriangle } from 'lucide-react';
import type { Analysis } from '../lib/api';
import { format } from 'date-fns';

interface AnalysisDetailsProps {
  analysis: Analysis;
  onClose: () => void;
}

export function AnalysisDetails({ analysis, onClose }: AnalysisDetailsProps) {
  const getSeverityColor = (severity: string) => {
    switch (severity.toLowerCase()) {
      case 'critical':
      case 'high':
        return 'bg-red-100 text-red-800';
      case 'medium':
        return 'bg-yellow-100 text-yellow-800';
      case 'low':
        return 'bg-blue-100 text-blue-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  return (
    <div className="fixed inset-0 bg-gray-500 bg-opacity-75 flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-lg max-w-4xl w-full max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-200 flex justify-between items-center">
          <div>
            <h3 className="text-lg font-medium text-gray-900">
              Analysis Details - #{analysis.id.slice(0, 8)}
            </h3>
            <p className="text-sm text-gray-500 mt-1">
              Created {format(new Date(analysis.created_at), 'MMM dd, yyyy HH:mm')}
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-500"
          >
            <X className="h-6 w-6" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {analysis.status === 'completed' ? (
            <div className="space-y-6">
              {/* Summary */}
              {analysis.summary && (
                <div>
                  <h4 className="text-sm font-medium text-gray-900 mb-2">Summary</h4>
                  <p className="text-sm text-gray-700 bg-gray-50 p-4 rounded-md">
                    {analysis.summary}
                  </p>
                </div>
              )}

              {/* Metrics */}
              <div className="grid grid-cols-2 gap-4">
                {analysis.cluster_count !== undefined && (
                  <div className="bg-blue-50 p-4 rounded-md">
                    <p className="text-sm text-blue-600 font-medium">Clusters Found</p>
                    <p className="text-2xl font-bold text-blue-900 mt-1">
                      {analysis.cluster_count}
                    </p>
                  </div>
                )}
                {analysis.severity_score !== undefined && (
                  <div className="bg-orange-50 p-4 rounded-md">
                    <p className="text-sm text-orange-600 font-medium">Severity Score</p>
                    <p className="text-2xl font-bold text-orange-900 mt-1">
                      {analysis.severity_score.toFixed(1)}/10
                    </p>
                  </div>
                )}
              </div>

              {/* Clusters */}
              {analysis.clusters && analysis.clusters.length > 0 && (
                <div>
                  <h4 className="text-sm font-medium text-gray-900 mb-3">Log Clusters</h4>
                  <div className="space-y-4">
                    {analysis.clusters.map((cluster) => (
                      <div
                        key={cluster.cluster_id}
                        className="border border-gray-200 rounded-md p-4"
                      >
                        <div className="flex items-start justify-between mb-3">
                          <div className="flex-1">
                            <div className="flex items-center gap-3">
                              <h5 className="text-sm font-medium text-gray-900">
                                {cluster.label}
                              </h5>
                              <span
                                className={`px-2 py-1 text-xs font-semibold rounded-full ${getSeverityColor(
                                  cluster.severity
                                )}`}
                              >
                                {cluster.severity}
                              </span>
                            </div>
                            <p className="text-sm text-gray-500 mt-1">
                              {cluster.size} similar log{cluster.size !== 1 ? 's' : ''}
                            </p>
                          </div>
                        </div>

                        {cluster.sample_logs && cluster.sample_logs.length > 0 && (
                          <div className="mt-3">
                            <p className="text-xs font-medium text-gray-700 mb-2">
                              Sample Logs:
                            </p>
                            <div className="bg-gray-50 rounded p-3 space-y-2">
                              {cluster.sample_logs.slice(0, 3).map((log, idx) => (
                                <p key={idx} className="text-xs text-gray-600 font-mono">
                                  {log}
                                </p>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : analysis.status === 'failed' ? (
            <div className="flex items-center justify-center py-12">
              <div className="text-center">
                <AlertTriangle className="h-12 w-12 text-red-600 mx-auto mb-4" />
                <h4 className="text-lg font-medium text-gray-900 mb-2">Analysis Failed</h4>
                {analysis.error && (
                  <p className="text-sm text-gray-600">{analysis.error}</p>
                )}
              </div>
            </div>
          ) : (
            <div className="flex items-center justify-center py-12">
              <div className="text-center">
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
                <h4 className="text-lg font-medium text-gray-900 mb-2">
                  Analysis {analysis.status}...
                </h4>
                <p className="text-sm text-gray-600">This may take a few moments</p>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-gray-200 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
