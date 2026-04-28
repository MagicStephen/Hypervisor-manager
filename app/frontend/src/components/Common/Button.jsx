import React, { useEffect, useRef } from 'react';
import bootstrap from 'bootstrap/dist/js/bootstrap.bundle.min.js';

function Button({
  className = "",
  onClick,
  style,
  children,
  tooltip
}) {
  const btnRef = useRef(null);
  const tooltipInstance = useRef(null);

  useEffect(() => {
    if (tooltip && btnRef.current) {
      // vytvoříme tooltip pouze jednou
      tooltipInstance.current = new bootstrap.Tooltip(btnRef.current, {
        placement: 'right',
      });
    }
    return () => {
      // cleanup tooltipu při unmountu
      if (tooltipInstance.current) {
        tooltipInstance.current.dispose();
      }
    };
  }, []); // ← prázdné pole závislostí, inicializace jen jednou

  return (
    <button
      ref={btnRef}
      className={`btn ${className} w-100 d-flex justify-content-center align-items-center`}
      onClick={onClick}
      style={{ ...style }}
      title={tooltip} 
    >
      {children}
    </button>
  );
}

export default Button;
