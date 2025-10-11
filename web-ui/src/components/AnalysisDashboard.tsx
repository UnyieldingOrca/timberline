import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { Plus, Trash2, RefreshCw, AlertCircle, CheckCircle, Clock, Sparkles, TrendingUp, BarChart3, Layers } from 'lucide-react';
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
        return <CheckCircle className="h-5 w-5 text-emerald-600" />;
      case 'failed':
        return <AlertCircle className="h-5 w-5 text-red-600" />;
      case 'running':
        return <RefreshCw className="h-5 w-5 text-blue-600 animate-spin" />;
      default:
        return <Clock className="h-5 w-5 text-slate-400" />;
    }
  };

  const getStatusColor = (status: Analysis['status']) => {
    switch (status) {
      case 'completed':
        return 'bg-emerald-100 text-emerald-700 border-emerald-200';
      case 'failed':
        return 'bg-red-100 text-red-700 border-red-200';
      case 'running':
        return 'bg-blue-100 text-blue-700 border-blue-200';
      default:
        return 'bg-slate-100 text-slate-700 border-slate-200';
    }
  };

  const getSeverityColor = (score?: number) => {
    if (!score) return 'text-slate-600';
    if (score >= 8) return 'text-red-600';
    if (score >= 6) return 'text-orange-600';
    if (score >= 4) return 'text-amber-600';
    return 'text-emerald-600';
  };

  const completedCount = analyses?.filter(a => a.status === 'completed').length || 0;
  const runningCount = analyses?.filter(a => a.status === 'running').length || 0;
  const failedCount = analyses?.filter(a => a.status === 'failed').length || 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h2 className="text-3xl font-bold text-slate-900 flex items-center gap-3">
            <Sparkles className="h-8 w-8 text-blue-600" />
            AI Analysis
          </h2>
          <p className="text-sm text-slate-500 mt-1">Intelligent log clustering and insights</p>
        </div>
        <div className="flex gap-3">
          <button
            onClick={() => refetch()}
            className="inline-flex items-center gap-2 px-4 py-2.5 bg-white border border-slate-200 rounded-lg shadow-sm text-sm font-semibold text-slate-700 hover:bg-slate-50 hover:border-slate-300 transition-all duration-200"
          >
            <RefreshCw className="h-4 w-4" />
            Refresh
          </button>
          <button
            onClick={() => setShowCreateModal(true)}
            className="inline-flex items-center gap-2 px-4 py-2.5 bg-gradient-to-r from-blue-600 to-indigo-600 rounded-lg shadow-sm text-sm font-semibold text-white hover:from-blue-700 hover:to-indigo-700 transition-all duration-200"
          >
            <Plus className="h-4 w-4" />
            New Analysis
          </button>
        </div>
      </div>

      {/* Quick Stats */}
      {analyses && analyses.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="bg-white rounded-xl p-4 border border-slate-200 shadow-sm">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-medium text-slate-500 uppercase">Total Analyses</p>
                <p className="text-2xl font-bold text-slate-900 mt-1">{analyses.length}</p>
              </div>
              <div className="p-3 bg-slate-100 rounded-lg">
                <BarChart3 className="h-5 w-5 text-slate-600" />
              </div>
            </div>
          </div>
          <div className="bg-white rounded-xl p-4 border border-emerald-200 shadow-sm">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-medium text-emerald-500 uppercase">Completed</p>
                <p className="text-2xl font-bold text-emerald-700 mt-1">{completedCount}</p>
              </div>
              <div className="p-3 bg-emerald-100 rounded-lg">
                <CheckCircle className="h-5 w-5 text-emerald-600" />
              </div>
            </div>
          </div>
          <div className="bg-white rounded-xl p-4 border border-blue-200 shadow-sm">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-medium text-blue-500 uppercase">Running</p>
                <p className="text-2xl font-bold text-blue-700 mt-1">{runningCount}</p>
              </div>
              <div className="p-3 bg-blue-100 rounded-lg">
                <RefreshCw className="h-5 w-5 text-blue-600" />
              </div>
            </div>
          </div>
          <div className="bg-white rounded-xl p-4 border border-red-200 shadow-sm">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-medium text-red-500 uppercase">Failed</p>
                <p className="text-2xl font-bold text-red-700 mt-1">{failedCount}</p>
              </div>
              <div className="p-3 bg-red-100 rounded-lg">
                <AlertCircle className="h-5 w-5 text-red-600" />
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Analyses List */}
      <div className="bg-white/80 backdrop-blur-sm rounded-xl border border-slate-200 shadow-lg overflow-hidden">
        {isLoading ? (
          <div className="p-12 text-center">
            <RefreshCw className="h-8 w-8 text-blue-500 animate-spin mx-auto mb-3" />
            <p className="text-slate-600 font-medium">Loading analyses...</p>
          </div>
        ) : error ? (
          <div className="p-12 text-center">
            <AlertCircle className="h-8 w-8 text-red-500 mx-auto mb-3" />
            <p className="text-red-600 font-medium">
              Error loading analyses: {error instanceof Error ? error.message : 'Unknown error'}
            </p>
          </div>
        ) : !analyses || analyses.length === 0 ? (
          <div className="p-12 text-center">
            <Sparkles className="h-12 w-12 text-slate-400 mx-auto mb-4" />
            <p className="text-slate-600 font-medium text-lg mb-2">No analyses yet</p>
            <p className="text-slate-500 text-sm">Click "New Analysis" to get started with AI-powered log insights</p>
          </div>
        ) : (
          <div className="divide-y divide-slate-200">
            {analyses.map((analysis, index) => (
              <div
                key={analysis.id}
                className="p-6 hover:bg-slate-50 cursor-pointer transition-all duration-150 group"
                onClick={() => setSelectedAnalysis(analysis)}
                style={{ animationDelay: `${index * 50}ms` }}
              >
                <div className="flex items-start justify-between">
                  <div className="flex items-start gap-4 flex-1">
                    <div className="p-3 bg-gradient-to-br from-blue-50 to-indigo-50 rounded-xl group-hover:scale-105 transition-transform">
                      {getStatusIcon(analysis.status)}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-3 flex-wrap">
                        <p className="text-base font-bold text-slate-900">
                          Analysis #{analysis.id.slice(0, 8)}
                        </p>
                        <span
                          className={`px-3 py-1 inline-flex text-xs font-bold rounded-full border ${getStatusColor(
                            analysis.status
                          )}`}
                        >
                          {analysis.status}
                        </span>
                      </div>
                      <p className="text-sm text-slate-500 mt-1 flex items-center gap-2">
                        <Clock className="h-4 w-4" />
                        {format(new Date(analysis.created_at), 'MMM dd, yyyy HH:mm')}
                      </p>
                      {analysis.summary && (
                        <p className="text-sm text-slate-700 mt-3 leading-relaxed line-clamp-2">
                          {analysis.summary}
                        </p>
                      )}
                      {analysis.status === 'completed' && (
                        <div className="flex gap-6 mt-3">
                          {analysis.cluster_count !== undefined && (
                            <div className="flex items-center gap-2 text-sm">
                              <div className="p-1.5 bg-blue-100 rounded-lg">
                                <Layers className="h-4 w-4 text-blue-600" />
                              </div>
                              <span className="font-semibold text-slate-700">{analysis.cluster_count} clusters</span>
                            </div>
                          )}
                          {analysis.severity_score !== undefined && (
                            <div className="flex items-center gap-2 text-sm">
                              <div className="p-1.5 bg-amber-100 rounded-lg">
                                <TrendingUp className="h-4 w-4 text-amber-600" />
                              </div>
                              <span className="font-semibold text-slate-700">
                                Severity: <span className={getSeverityColor(analysis.severity_score)}>{analysis.severity_score.toFixed(1)}/10</span>
                              </span>
                            </div>
                          )}
                        </div>
                      )}
                      {analysis.error && (
                        <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-lg">
                          <p className="text-sm text-red-700 font-medium">{analysis.error}</p>
                        </div>
                      )}
                    </div>
                  </div>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDelete(analysis.id);
                    }}
                    className="ml-4 p-2 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-all duration-200"
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
