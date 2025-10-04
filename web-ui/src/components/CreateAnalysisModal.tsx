import { useState } from 'react';
import { X } from 'lucide-react';
import { analysisApi } from '../lib/api';
import type { CreateAnalysisRequest } from '../lib/api';

interface CreateAnalysisModalProps {
  onClose: () => void;
  onCreated: () => void;
}

export function CreateAnalysisModal({ onClose, onCreated }: CreateAnalysisModalProps) {
  const [namespace, setNamespace] = useState('');
  const [timeRangeHours, setTimeRangeHours] = useState('24');
  const [minClusterSize, setMinClusterSize] = useState('5');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setIsSubmitting(true);

    try {
      const request: CreateAnalysisRequest = {
        namespace: namespace || undefined,
        time_range_hours: parseInt(timeRangeHours) || undefined,
        min_cluster_size: parseInt(minClusterSize) || undefined,
      };

      await analysisApi.createAnalysis(request);
      onCreated();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create analysis');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-gray-500 bg-opacity-75 flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-lg max-w-md w-full p-6">
        <div className="flex justify-between items-center mb-4">
          <h3 className="text-lg font-medium text-gray-900">Create New Analysis</h3>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-500"
          >
            <X className="h-6 w-6" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="namespace" className="block text-sm font-medium text-gray-700">
              Namespace (optional)
            </label>
            <input
              id="namespace"
              type="text"
              value={namespace}
              onChange={(e) => setNamespace(e.target.value)}
              placeholder="Leave empty for all namespaces"
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
            />
            <p className="mt-1 text-sm text-gray-500">
              Analyze logs from a specific namespace, or all if left empty
            </p>
          </div>

          <div>
            <label htmlFor="timeRange" className="block text-sm font-medium text-gray-700">
              Time Range (hours)
            </label>
            <input
              id="timeRange"
              type="number"
              value={timeRangeHours}
              onChange={(e) => setTimeRangeHours(e.target.value)}
              min="1"
              max="168"
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
            />
            <p className="mt-1 text-sm text-gray-500">
              How far back to analyze (1-168 hours)
            </p>
          </div>

          <div>
            <label htmlFor="minClusterSize" className="block text-sm font-medium text-gray-700">
              Minimum Cluster Size
            </label>
            <input
              id="minClusterSize"
              type="number"
              value={minClusterSize}
              onChange={(e) => setMinClusterSize(e.target.value)}
              min="1"
              max="100"
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
            />
            <p className="mt-1 text-sm text-gray-500">
              Minimum number of similar logs to form a cluster
            </p>
          </div>

          {error && (
            <div className="rounded-md bg-red-50 p-4">
              <p className="text-sm text-red-800">{error}</p>
            </div>
          )}

          <div className="flex justify-end gap-3 pt-4">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isSubmitting ? 'Creating...' : 'Create Analysis'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
