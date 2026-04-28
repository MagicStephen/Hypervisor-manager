import React from "react";

function Spinner({ loading }) {
  if (!loading) return null;

  return (
    <div
      className="position-absolute top-0 start-0 w-100 h-100 d-flex justify-content-center align-items-center rounded"
      style={{
        backgroundColor: "rgba(0, 0, 0, 0.85)", 
        backdropFilter: "blur(1px)", 
        zIndex: 10,
      }}
    >
      <div
        className="spinner-border text-light"
        role="status"
        style={{
          width: "4rem",
          height: "4rem",
          boxShadow: "0 0 10px rgba(0,0,0,0.2)",
        }}
      >
        <span className="visually-hidden">Loading...</span>
      </div>
    </div>
  );
}

export default Spinner;