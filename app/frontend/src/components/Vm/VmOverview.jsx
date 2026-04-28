import MetricChart from '../Common/MetricChart';
import React, { useEffect, useState } from 'react';
import Spinner from '../Common/Spinner';
import { fetchVmTimeMetrics } from '../../services/VmService';

function VmOverview({ selectedItem }) {
  const [metrics, setMetrics] = useState([]);
  const [loading, setLoading] = useState(false);

  const metricHistory = Array.isArray(metrics) ? metrics : [];

  const cpuChartData = metricHistory.map((item, index) => ({
    time: item.time || `${index}`,
    value: (Number(item.cpu_usage) || 0) * 100,
  }));

  const memoryChartData = metricHistory.map((item, index) => ({
    time: item.time || `${index}`,
    value: Number(item.memory_used) || 0,
  }));

  const toNumber = (value) => Number(value) || 0;
  const bytesToKb = (value) => toNumber(value) / 1024;

  const networkChartData = metricHistory.map((item, index) => ({
    time: item.time || `${index}`,
    net_in: bytesToKb(item.net_in ?? item.netin),
    net_out: bytesToKb(item.net_out ?? item.netout),
  }));

  const diskChartData = metricHistory.map((item, index) => ({
    time: item.time || `${index}`,
    disk_read: bytesToKb(item.disk_read ?? item.diskread),
    disk_write: bytesToKb(item.disk_write ?? item.diskwrite),
  }));


  async function loadVmMetrics(currentServerId, currentNodeId, currentVmId) {
    return await fetchVmTimeMetrics(currentServerId, currentNodeId, currentVmId, {
      timeframe: 'hour',
      fields: [
        'cpu_usage',
        'memory_used',
        'memory_total',
        'net_in',
        'net_out',
        'disk_read',
        'disk_write',
      ],
    });
  }

  useEffect(() => {
    if (
      selectedItem?.serverId == null ||
      selectedItem?.nodeId == null ||
      selectedItem?.id == null
    ) {
      setMetrics([]);
      return;
    }

    let isMounted = true;

    async function loadData(showSpinner = false) {
      try {
        if (showSpinner) setLoading(true);

        const result = await loadVmMetrics(
          selectedItem.serverId,
          selectedItem.nodeId,
          selectedItem.id
        );

        if (isMounted) {
          setMetrics(Array.isArray(result) ? result : []);
        }
      } catch (error) {
        console.error('Error loading VM metrics:', error);
        if (isMounted) setMetrics([]);
      } finally {
        if (isMounted && showSpinner) setLoading(false);
      }
    }

    loadData(true);

    const intervalId = setInterval(() => {
      loadData(false);
    }, 5000);

    return () => {
      isMounted = false;
      clearInterval(intervalId);
    };
  }, [selectedItem?.serverId, selectedItem?.nodeId, selectedItem?.id]);

  return (
    <div className="col-12 h-100 ps-0 pe-0">
      <Spinner loading={loading} />

      <div className="row h-100 m-0">
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

        <div className="col-6 ps-1 pb-1 h-50">
          <div className="card h-100">
            <MetricChart
              title="Memory usage"
              data={memoryChartData}
              unit="memory_gb"
              color="#fd7e14"
            />
          </div>
        </div>

        <div className="col-6 pe-1 pt-1 h-50">
          <div className="card h-100">
            <MetricChart
              title="Network traffic"
              data={networkChartData}
              unit="traffic"
              series={[
                { dataKey: 'net_in', name: 'In', color: '#0d6efd' },
                { dataKey: 'net_out', name: 'Out', color: '#198754' },
              ]}
            />
          </div>
        </div>

        <div className="col-6 ps-1 pt-1 h-50">
          <div className="card h-100">
            <MetricChart
              title="Disk I/O"
              data={diskChartData}
              unit="traffic"
              series={[
                { dataKey: 'disk_read', name: 'Read', color: '#6f42c1' },
                { dataKey: 'disk_write', name: 'Write', color: '#dc3545' },
              ]}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

export default VmOverview;