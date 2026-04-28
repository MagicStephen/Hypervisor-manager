function Modal({ show, onClose, title, backgroundColor = "white", color = "black", children }) {
  if (!show) return null;

  return (
    <div className="modal fade show d-block" style={{ backgroundColor: "rgba(0,0,0,0.5)" }}>
      <div className="modal-dialog modal-dialog-centered modal-xl">
        <div className="modal-content" >
          <div className="modal-header">
            <h1 className="modal-title fs-5" id="exampleModalLabel">{title}</h1>
            <button type="button" className="btn-close" data-bs-dismiss="modal" aria-label="Close" onClick={onClose}></button>
          </div>
          <div className="modal-body">
            {children} {/* sem vložíme form */}
          </div>
        </div>
      </div>
    </div>
  );
}

export default Modal;
