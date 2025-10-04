import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { Plus, Trash2, RefreshCw, AlertCircle, CheckCircle, Clock } from 'lucide-react';
import { analysisApi } from '../lib/api';
import type { Analysis } from '../lib/api';
import { format } from 'date-fns';
import { CreateAnalysisModal } from './CreateAnalysisModal';
import { AnalysisDetails } from './AnalysisDetails';

export function AnalysisDashboard() {
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [selectedAnalysis, setSelectedAnalysis] = useState<Analysis | null>(null);

  const { data: analyses, isLoading, error, refetch } = useQuery({
    queryKey: ['analyses'],
    queryFn: analysisApi.getAnalyses,
    refetchInterval: 5000, // Refresh every 5 seconds for status updates
  });

  const handleDelete = async (id: string) => {
    if (confirm('Are you sure you want to delete this analysis?')) {
      await analysisApi.deleteAnalysis(id);
      refetch();
    }
  };

  const getStatusIcon = (status: Analysis['status']) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="h-5 w-5 text-green-600" />;
      case 'failed':
        return <AlertCircle className="h-5 w-5 text-red-600" />;
      case 'running':
        return <RefreshCw className="h-5 w-5 text-blue-600 animate-spin" />;
      default:
        return <Clock className="h-5 w-5 text-gray-400" />;
    }
  };

  const getStatusColor = (status: Analysis['status']) => {
    switch (status) {
      case 'completed':
        return 'bg-green-100 text-green-800';
      case 'failed':
        return 'bg-red-100 text-red-800';
      case 'running':
        return 'bg-blue-100 text-blue-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <h2 className="text-2xl font-bold text-gray-900">AI Analysis</h2>
        <div className="flex gap-3">
          <button
            onClick={() => refetch()}
            className="inline-flex items-center px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
          >
            <RefreshCw className="h-4 w-4 mr-2" />
            Refresh
          </button>
          <button
            onClick={() => setShowCreateModal(true)}
            className="inline-flex items-center px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
          >
            <Plus className="h-4 w-4 mr-2" />
            New Analysis
          </button>
        </div>
      </div>

      {/* Analyses List */}
      <div className="bg-white rounded-lg shadow overflow-hidden">
        {isLoading ? (
          <div className="p-8 text-center text-gray-500">Loading analyses...</div>
        ) : error ? (
          <div className="p-8 text-center text-red-600">
            Error loading analyses: {error instanceof Error ? error.message : 'Unknown error'}
          </div>
        ) : !analyses || analyses.length === 0 ? (
          <div className="p-8 text-center text-gray-500">
            No analyses yet. Click "New Analysis" to get started.
          </div>
        ) : (
          <div className="divide-y divide-gray-200">
            {analyses.map((analysis) => (
              <div
                key={analysis.id}
                className="p-6 hover:bg-gray-50 cursor-pointer"
                onClick={() => setSelectedAnalysis(analysis)}
              >
                <div className="flex items-start justify-between">
                  <div className="flex items-start space-x-3 flex-1">
                    {getStatusIcon(analysis.status)}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-3">
                        <p className="text-sm font-medium text-gray-900">
                          Analysis #{analysis.id.slice(0, 8)}
                        </p>
                        <span
                          className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${getStatusColor(
                            analysis.status
                          )}`}
                        >
                          {analysis.status}
                        </span>
                      </div>
                      <p className="text-sm text-gray-500 mt-1">
                        Created {format(new Date(analysis.created_at), 'MMM dd, yyyy HH:mm')}
                      </p>
                      {analysis.summary && (
                        <p className="text-sm text-gray-700 mt-2 line-clamp-2">
                          {analysis.summary}
                        </p>
                      )}
                      {analysis.status === 'completed' && (
                        <div className="flex gap-4 mt-2 text-sm text-gray-600">
                          {analysis.cluster_count !== undefined && (
                            <span>{analysis.cluster_count} clusters found</span>
                          )}
                          {analysis.severity_score !== undefined && (
                            <span>Severity: {analysis.severity_score.toFixed(1)}/10</span>
                          )}
                        </div>
                      )}
                      {analysis.error && (
                        <p className="text-sm text-red-600 mt-2">{analysis.error}</p>
                      )}
                    </div>
                  </div>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDelete(analysis.id);
                    }}
                    className="ml-4 text-gray-400 hover:text-red-600"
                  >
                    <Trash2 className="h-5 w-5" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Create Analysis Modal */}
      {showCreateModal && (
        <CreateAnalysisModal
          onClose={() => setShowCreateModal(false)}
          onCreated={() => {
            setShowCreateModal(false);
            refetch();
          }}
        />
      )}

      {/* Analysis Details Modal */}
      {selectedAnalysis && (
        <AnalysisDetails
          analysis={selectedAnalysis}
          onClose={() => setSelectedAnalysis(null)}
        />
      )}
    </div>
  );
}
