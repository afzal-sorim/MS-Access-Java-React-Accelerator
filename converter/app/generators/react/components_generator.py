"""Shared Component Library Generator — generates reusable React UI primitives.

Every generated React application gets a `src/components/common/` directory
containing these shared components. Page generators import them instead of
repeating raw HTML elements inline.

Generated components use CSS Modules (`.module.css`) for scoped styles.
"""
from __future__ import annotations

from pathlib import PurePosixPath


class ComponentsGenerator:
    """Generates shared React component files for the output application.

    Usage:
        gen = ComponentsGenerator()
        files = gen.generate(src / "components" / "common")
    """

    def generate(self, output_dir) -> dict[str, str]:
        """Generate all shared components and return file-path → content map."""
        output_dir = PurePosixPath(str(output_dir))
        files: dict[str, str] = {}

        # Core UI components
        files[str(output_dir / "Button.jsx")] = self._button_jsx()
        files[str(output_dir / "Button.module.css")] = self._button_css()

        files[str(output_dir / "FormField.jsx")] = self._form_field_jsx()
        files[str(output_dir / "FormField.module.css")] = self._form_field_css()

        files[str(output_dir / "DataTable.jsx")] = self._data_table_jsx()
        files[str(output_dir / "DataTable.module.css")] = self._data_table_css()

        files[str(output_dir / "LoadingSpinner.jsx")] = self._loading_spinner_jsx()
        files[str(output_dir / "LoadingSpinner.module.css")] = self._loading_spinner_css()

        files[str(output_dir / "ErrorMessage.jsx")] = self._error_message_jsx()

        files[str(output_dir / "EmptyState.jsx")] = self._empty_state_jsx()

        files[str(output_dir / "PageHeader.jsx")] = self._page_header_jsx()
        files[str(output_dir / "PageHeader.module.css")] = self._page_header_css()

        files[str(output_dir / "Card.jsx")] = self._card_jsx()
        files[str(output_dir / "Card.module.css")] = self._card_css()

        files[str(output_dir / "InfoField.jsx")] = self._info_field_jsx()

        files[str(output_dir / "ErrorBoundary.jsx")] = self._error_boundary_jsx()

        # Barrel export
        files[str(output_dir / "index.js")] = self._barrel_export()

        return files

    # ---------------------------------------------------------------- Button

    @staticmethod
    def _button_jsx() -> str:
        return """import React from 'react';

/**
 * Reusable button component with primary/secondary/danger variants.
 */
export default function Button({
  children,
  type = 'button',
  variant = 'primary',
  size = 'md',
  disabled = false,
  loading = false,
  onClick,
  className = '',
  ...rest
}) {
  const classes = [
    'btn',
    variant === 'secondary' ? 'btn-secondary' : '',
    variant === 'danger' ? 'btn-danger' : '',
    loading ? 'loading' : '',
    className,
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <button
      type={type}
      className={classes}
      disabled={disabled || loading}
      onClick={onClick}
      {...rest}
    >
      {loading ? 'Loading\u2026' : children}
    </button>
  );
}
"""

    @staticmethod
    def _button_css() -> str:
        return """.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  padding: 0.625rem 1.25rem;
  border-radius: var(--radius-md, 8px);
  border: none;
  cursor: pointer;
  font-weight: 600;
  font-size: 0.875rem;
  line-height: 1.5;
  transition: all 0.2s ease;
  text-decoration: none;
}

.btn:focus-visible {
  outline: 2px solid var(--color-primary, #3b82f6);
  outline-offset: 2px;
}

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* Variants */
.primary {
  background: var(--color-primary, #3b82f6);
  color: #fff;
}

.primary:hover:not(:disabled) {
  filter: brightness(1.1);
  transform: translateY(-1px);
}

.secondary {
  background: var(--color-white, #fff);
  color: var(--color-text, #1f2937);
  border: 1px solid var(--color-border, #e5e7eb);
}

.secondary:hover:not(:disabled) {
  background: var(--color-bg, #f3f4f6);
  border-color: var(--color-primary, #3b82f6);
  color: var(--color-primary, #3b82f6);
}

.danger {
  background: #ef4444;
  color: #fff;
}

.danger:hover:not(:disabled) {
  background: #dc2626;
}

/* Sizes */
.sm { padding: 0.375rem 0.75rem; font-size: 0.8125rem; }
.md { padding: 0.625rem 1.25rem; font-size: 0.875rem; }
.lg { padding: 0.75rem 1.5rem; font-size: 1rem; }

.loading {
  position: relative;
  color: transparent;
}
"""

    # ---------------------------------------------------------------- FormField

    @staticmethod
    def _form_field_jsx() -> str:
        return """import React from 'react';

/**
 * Unified form field component supporting text, select, checkbox, textarea, and more.
 */
export default function FormField({
  label,
  name,
  type = 'text',
  value,
  onChange,
  required = false,
  disabled = false,
  options = [],
  placeholder = '',
  error = '',
  rows = 4,
}) {
  const id = `field-${name}`;

  if (type === 'checkbox') {
    return (
      <div className="form-group">
        <label>
          <input
            type="checkbox"
            name={name}
            checked={!!value}
            onChange={onChange}
            disabled={disabled}
            aria-describedby={error ? `${id}-error` : undefined}
          />
          {label}
        </label>
        {error && (
          <span id={`${id}-error`} className="error" role="alert">
            {error}
          </span>
        )}
      </div>
    );
  }

  if (type === 'select') {
    return (
      <div className="form-group">
        <label htmlFor={id}>
          {label}
          {required && <span className="required"> *</span>}
        </label>
        <select
          id={id}
          name={name}
          value={value || ''}
          onChange={onChange}
          disabled={disabled}
          aria-describedby={error ? `${id}-error` : undefined}
        >
          <option value="">Select\u2026</option>
          {options.map((opt) => (
            <option key={opt.value ?? opt} value={opt.value ?? opt}>
              {opt.label ?? opt}
            </option>
          ))}
        </select>
        {error && (
          <span id={`${id}-error`} className="error" role="alert">
            {error}
          </span>
        )}
      </div>
    );
  }

  if (type === 'textarea') {
    return (
      <div className="form-group">
        <label htmlFor={id}>
          {label}
          {required && <span className="required"> *</span>}
        </label>
        <textarea
          id={id}
          name={name}
          value={value || ''}
          onChange={onChange}
          disabled={disabled}
          rows={rows}
          placeholder={placeholder}
          aria-describedby={error ? `${id}-error` : undefined}
        />
        {error && (
          <span id={`${id}-error`} className="error" role="alert">
            {error}
          </span>
        )}
      </div>
    );
  }

  return (
    <div className="form-group">
      <label htmlFor={id}>
        {label}
        {required && <span className="required"> *</span>}
      </label>
      <input
        type={type}
        id={id}
        name={name}
        value={value || ''}
        onChange={onChange}
        required={required}
        disabled={disabled}
        placeholder={placeholder}
        aria-describedby={error ? `${id}-error` : undefined}
      />
      {error && (
        <span id={`${id}-error`} className="error" role="alert">
          {error}
        </span>
      )}
    </div>
  );
}
"""

    @staticmethod
    def _form_field_css() -> str:
        return """.formGroup {
  margin-bottom: 1.5rem;
}

.label {
  display: block;
  margin-bottom: 0.5rem;
  font-weight: 600;
  font-size: 0.875rem;
  color: var(--color-text, #1f2937);
}

.required {
  color: #ef4444;
}

.checkboxLabel {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-weight: 500;
  font-size: 0.875rem;
  cursor: pointer;
}

.input,
.select,
.textarea {
  width: 100%;
  padding: 0.625rem 0.75rem;
  border: 1px solid var(--color-border, #e5e7eb);
  border-radius: var(--radius-md, 8px);
  background: #fff;
  font-size: 0.875rem;
  color: var(--color-text, #1f2937);
  transition: border-color 0.2s ease;
}

.input:focus,
.select:focus,
.textarea:focus {
  outline: none;
  border-color: var(--color-primary, #3b82f6);
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.15);
}

.input:disabled,
.select:disabled,
.textarea:disabled {
  background: var(--color-bg, #f3f4f6);
  cursor: not-allowed;
  opacity: 0.7;
}

.textarea {
  resize: vertical;
  min-height: 80px;
}

.error {
  display: block;
  margin-top: 0.375rem;
  font-size: 0.8125rem;
  color: #ef4444;
}
"""

    # ---------------------------------------------------------------- DataTable

    @staticmethod
    def _data_table_jsx() -> str:
        return """import React from 'react';

/**
 * Reusable data table with sortable column headers and empty-state support.
 */
export default function DataTable({
  columns = [],
  data = [],
  onRowClick,
  emptyMessage = 'No records found.',
  keyField = 'id',
}) {
  const safeData = Array.isArray(data) ? data : (data?.content || (data ? [data] : []));
  
  if (safeData.length === 0) {
    return <p className="empty">{emptyMessage}</p>;
  }

  return (
    <div className="table-wrapper">
      <table className="data-table">
        <thead>
          <tr>
            {columns.map((col) => (
              <th
                key={col.key}
                style={col.align ? { textAlign: col.align } : undefined}
              >
                {col.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {safeData.map((row, index) => (
            <tr
              key={row[keyField] ?? index}
              onClick={onRowClick ? () => onRowClick(row) : undefined}
              style={onRowClick ? { cursor: 'pointer' } : undefined}
            >
              {columns.map((col) => (
                <td
                  key={col.key}
                  style={col.align ? { textAlign: col.align } : undefined}
                >
                  {row[col.key] === null || row[col.key] === undefined
                    ? '\u2014'
                    : String(row[col.key])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
"""

    @staticmethod
    def _data_table_css() -> str:
        return """.wrapper {
  overflow-x: auto;
  margin: 1.5rem 0;
}

.table {
  width: 100%;
  border-collapse: collapse;
  background: #fff;
  border-radius: var(--radius-md, 8px);
  overflow: hidden;
  box-shadow: var(--shadow-sm, 0 1px 2px rgba(0, 0, 0, 0.05));
}

.table th,
.table td {
  padding: 0.75rem 1rem;
  text-align: left;
  border-bottom: 1px solid var(--color-border, #e5e7eb);
}

.table th {
  background: #f8fafc;
  font-weight: 700;
  font-size: 0.8125rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--color-text, #1f2937);
}

.table tr:last-child td {
  border-bottom: none;
}

.clickable {
  cursor: pointer;
  transition: background 0.15s ease;
}

.clickable:hover {
  background: var(--color-bg, #f3f4f6);
}

.empty {
  text-align: center;
  padding: 2rem;
  color: var(--color-text-muted, #6b7280);
  font-style: italic;
}
"""

    # ---------------------------------------------------------------- LoadingSpinner

    @staticmethod
    def _loading_spinner_jsx() -> str:
        return """import React from 'react';
import styles from './LoadingSpinner.module.css';

/**
 * Accessible loading spinner with optional message.
 */
export default function LoadingSpinner({ message = 'Loading\u2026' }) {
  return (
    <div className={styles.container} role="status" aria-live="polite">
      <div className={styles.spinner} aria-hidden="true" />
      <p className={styles.message}>{message}</p>
    </div>
  );
}
"""

    @staticmethod
    def _loading_spinner_css() -> str:
        return """.container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 3rem 1rem;
  gap: 1rem;
}

.spinner {
  width: 2.5rem;
  height: 2.5rem;
  border: 3px solid var(--color-border, #e5e7eb);
  border-top-color: var(--color-primary, #3b82f6);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.message {
  color: var(--color-text-muted, #6b7280);
  font-size: 0.875rem;
}
"""

    # ---------------------------------------------------------------- ErrorMessage

    @staticmethod
    def _error_message_jsx() -> str:
        return """import React from 'react';

/**
 * Accessible error message display.
 */
export default function ErrorMessage({ message, onRetry }) {
  if (!message) return null;

  return (
    <div
      role="alert"
      style={{
        padding: '1rem 1.25rem',
        borderRadius: 'var(--radius-md, 8px)',
        background: '#fef2f2',
        border: '1px solid #fecaca',
        color: '#991b1b',
        fontSize: '0.875rem',
        display: 'flex',
        alignItems: 'center',
        gap: '0.75rem',
      }}
    >
      <span style={{ flex: 1 }}>{message}</span>
      {onRetry && (
        <button
          onClick={onRetry}
          style={{
            background: 'none',
            border: '1px solid #991b1b',
            borderRadius: '4px',
            color: '#991b1b',
            padding: '0.25rem 0.75rem',
            cursor: 'pointer',
            fontSize: '0.8125rem',
          }}
        >
          Retry
        </button>
      )}
    </div>
  );
}
"""

    # ---------------------------------------------------------------- EmptyState

    @staticmethod
    def _empty_state_jsx() -> str:
        return """import React from 'react';

/**
 * Placeholder component for pages/tables with no data.
 */
export default function EmptyState({
  title = 'No records found',
  description = 'There is no data to display at this time.',
  actionLabel,
  onAction,
}) {
  return (
    <div
      style={{
        textAlign: 'center',
        padding: '3rem 1rem',
        color: 'var(--color-text-muted, #6b7280)',
      }}
    >
      <h3 style={{ fontSize: '1.125rem', marginBottom: '0.5rem', color: 'var(--color-text, #1f2937)' }}>
        {title}
      </h3>
      <p style={{ fontSize: '0.875rem', marginBottom: '1.5rem' }}>{description}</p>
      {actionLabel && onAction && (
        <button
          onClick={onAction}
          style={{
            padding: '0.5rem 1rem',
            background: 'var(--color-primary, #3b82f6)',
            color: '#fff',
            border: 'none',
            borderRadius: 'var(--radius-md, 8px)',
            cursor: 'pointer',
            fontWeight: 600,
          }}
        >
          {actionLabel}
        </button>
      )}
    </div>
  );
}
"""

    # ---------------------------------------------------------------- PageHeader

    @staticmethod
    def _page_header_jsx() -> str:
        return """import React from 'react';

/**
 * Standard page header with title, optional subtitle, and action slot.
 */
export default function PageHeader({ title, subtitle, children }) {
  return (
    <div className="page-header">
      <div>
        <h1>{title}</h1>
        {subtitle && <p>{subtitle}</p>}
      </div>
      {children && <div className="page-header-actions">{children}</div>}
    </div>
  );
}
"""

    @staticmethod
    def _page_header_css() -> str:
        return """.header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 1.5rem;
  gap: 1rem;
  flex-wrap: wrap;
}

.title {
  font-size: 1.75rem;
  font-weight: 800;
  color: var(--color-text, #1f2937);
  margin: 0;
}

.subtitle {
  font-size: 0.875rem;
  color: var(--color-text-muted, #6b7280);
  margin-top: 0.25rem;
}

.actions {
  display: flex;
  gap: 0.75rem;
  align-items: center;
}
"""

    # ---------------------------------------------------------------- Card

    @staticmethod
    def _card_jsx() -> str:
        return """import React from 'react';

/**
 * Card container with optional title and accent color.
 */
export default function Card({ title, accent, children, className = '' }) {
  return (
    <div
      className={`card ${className}`}
      style={accent ? { borderTopColor: accent } : undefined}
    >
      {title && <h2>{title}</h2>}
      {children}
    </div>
  );
}
"""

    @staticmethod
    def _card_css() -> str:
        return """.card {
  background: var(--color-white);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg, 16px);
  padding: 2rem;
  box-shadow: var(--shadow-lg);
  border-top: 4px solid var(--color-primary);
  animation: fadeIn 0.4s ease-out;
  transition: transform 0.25s ease, box-shadow 0.25s ease;
}

.card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-glow);
}

.title {
  font-size: 1.5rem;
  font-weight: 700;
  margin: 0 0 1.5rem 0;
  color: var(--color-text);
  background: linear-gradient(135deg, var(--color-primary-light), var(--color-secondary));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}
"""

    # ---------------------------------------------------------------- InfoField

    @staticmethod
    def _info_field_jsx() -> str:
        return """import React from 'react';

/**
 * Read-only label/value pair for detail views.
 */
export default function InfoField({ label, value }) {
  return (
    <div className="info-field">
      <span className="info-label">
        {label}
      </span>
      <span className="info-value">
        {value ?? '\u2014'}
      </span>
    </div>
  );
}
"""

    # ---------------------------------------------------------------- ErrorBoundary

    @staticmethod
    def _error_boundary_jsx() -> str:
        return """import React from 'react';

/**
 * React Error Boundary — catches rendering errors and shows a fallback UI.
 */
export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('[ErrorBoundary]', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div
          role="alert"
          style={{
            padding: '2rem',
            margin: '2rem',
            background: '#fef2f2',
            borderRadius: '8px',
            border: '1px solid #fecaca',
            textAlign: 'center',
          }}
        >
          <h2 style={{ color: '#991b1b', marginBottom: '0.5rem' }}>
            Something went wrong
          </h2>
          <p style={{ color: '#7f1d1d', fontSize: '0.875rem' }}>
            {this.state.error?.message || 'An unexpected error occurred.'}
          </p>
          <button
            onClick={() => window.location.reload()}
            style={{
              marginTop: '1rem',
              padding: '0.5rem 1rem',
              background: '#991b1b',
              color: '#fff',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer',
            }}
          >
            Reload Page
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
"""

    # ---------------------------------------------------------------- Barrel export

    @staticmethod
    def _barrel_export() -> str:
        return """export { default as Button } from './Button';
export { default as FormField } from './FormField';
export { default as DataTable } from './DataTable';
export { default as LoadingSpinner } from './LoadingSpinner';
export { default as ErrorMessage } from './ErrorMessage';
export { default as EmptyState } from './EmptyState';
export { default as PageHeader } from './PageHeader';
export { default as Card } from './Card';
export { default as InfoField } from './InfoField';
export { default as ErrorBoundary } from './ErrorBoundary';
"""
