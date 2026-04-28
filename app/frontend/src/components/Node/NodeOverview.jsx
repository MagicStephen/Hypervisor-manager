import React, { useEffect, useState } from 'react';
import MetricChart from '../Common/MetricChart';
import Spinner from '../Common/Spinner';
import { fetchNodeMetrics } from '../../services/NodeService';
import {
  mapCpuChartData,
  mapMemoryChartData,
  mapLoadChartData,
  mapNetworkChartData,
  getHistoryItems
} from '../../utils/metrics/mappers';
import { NODE_METRIC_REQUEST } from '../../utils/node/constants';

function NodeOverview({ serverId, nodeId }) {
  const [metrics, setMetrics] = useState(null);
  const [loading, setLoading] = useState(false);

  const canLoadMetrics = serverId != null && nodeId != null;

  const historyItems = getHistoryItems(metrics);
  const cpuChartData = mapCpuChartData(historyItems);
  const memoryChartData = mapMemoryChartData(historyItems);
  const loadChartData = mapLoadChartData(historyItems);
  const networkChartData = mapNetworkChartData(historyItems);

  useEffect(() => {
    if (!canLoadMetrics) {
      setMetrics(null);
      return;
    }

    let isMounted = true;

    async function loadInitialData() {
      try {
        setLoading(true);

        const result = await fetchNodeMetrics(
          serverId,
          nodeId,
          NODE_METRIC_REQUEST
        );

        if (isMounted) {
          setMetrics(result);
        }
      } catch (error) {
        console.error('Error loading node metrics:', error);

        if (isMounted) {
          setMetrics(null);
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    }

    loadInitialData();

    const intervalId = setInterval(async () => {
      try {
        const result = await fetchNodeMetrics(
          serverId,
          nodeId,
          NODE_METRIC_REQUEST
        );

        if (isMounted && result) {
          setMetrics(result);
        }
      } catch (error) {
        console.error('Error refreshing node metrics:', error);
      }
    }, 5000);

    return () => {
      isMounted = false;
      clearInterval(intervalId);
    };
  }, [serverId, nodeId, canLoadMetrics]);

  return (
    <>
      <Spinner loading={loading} />

      <div className="col-6 pe-1 pb-1 h-50">
        <div className="card h-100">
          <MetricChart
            title="CPU usage"
            data={cpuChartData}
            unit="percent"
            yDomain={[0, 100]}
            color="#0d6efd"
          />
        </div>
      </div>

      {loadChartData.length > 0 && (
        <div className="col-6 ps-1 pb-1 h-50">
          <div className="card h-100">
            <MetricChart
              title="Server load"
              data={loadChartData}
              unit="load"
              color="#198754"
            />
          </div>
        </div>
      )}

      <div className="col-6 h-50 pe-1 pt-1">
        <div className="card h-100">
          <MetricChart
            title="Memory usage"
            data={memoryChartData}
            unit="memory_gb"
            color="#fd7e14"
          />
        </div>
      </div>

      <div className="col-6 h-50 ps-1 pt-1">
        <div className="card h-100">
          <MetricChart
            title="Network traffic"
            data={networkChartData}
            unit="traffic"
            series={[
              { dataKey: 'net_in', name: 'In', color: '#0d6efd' },
              { dataKey: 'net_out', name: 'Out', color: '#198754' }
            ]}
          />
        </div>
      </div>
    </>
  );
}

export default NodeOverview;