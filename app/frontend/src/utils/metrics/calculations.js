
export function getUsagePercent(total, used) {
  const totalNum = Number(total);
  const usedNum = Number(used);

  if (!Number.isFinite(totalNum) || !Number.isFinite(usedNum) || totalNum <= 0) {
    return 0;
  }

  return Math.min(100, Math.max(0, (usedNum / totalNum) * 100));
}

export function getLastValidValue(data, key) {
  for (let i = data.length - 1; i >= 0; i--) {
    const value = data[i]?.[key];

    if (value != null && !Number.isNaN(Number(value))) {
      return value;
    }
  }

  return null;
}