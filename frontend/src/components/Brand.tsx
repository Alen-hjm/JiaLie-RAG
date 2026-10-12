export function Brand() {
  return (
    <div className="brand">
      <span className="brand-mark" aria-hidden="true">
        <svg viewBox="0 0 32 32" fill="none">
          <path
            d="M7 23V9l9 7 9-7v14M7 9l9 14 9-14"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </span>
      <div>
        <strong>
          嘉猎<span>JIALIE</span>
        </strong>
        <small>让人才，被看见</small>
      </div>
    </div>
  );
}
