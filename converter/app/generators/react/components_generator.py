"""Reusable React component library emitted with every generated frontend.

Keeping these templates in one small generator makes the generated projects
consistent without coupling the Access form conversion code to one UI theme.
"""
from __future__ import annotations

from pathlib import Path


class ComponentsGenerator:
    """Build framework-agnostic React UI primitives and their CSS modules."""

    def generate(self, output_dir: str | Path) -> dict[str, str]:
        output_dir = Path(output_dir)
        templates = {
            "Button.jsx": self._button(),
            "Button.module.css": self._button_css(),
            "Card.jsx": self._card(),
            "Card.module.css": self._card_css(),
            "DataTable.jsx": self._data_table(),
            "DataTable.module.css": self._data_table_css(),
            "EmptyState.jsx": self._empty_state(),
            "ErrorBoundary.jsx": self._error_boundary(),
            "ErrorMessage.jsx": self._error_message(),
            "FormField.jsx": self._form_field(),
            "FormField.module.css": self._form_field_css(),
            "InfoField.jsx": self._info_field(),
            "LoadingSpinner.jsx": self._loading_spinner(),
            "LoadingSpinner.module.css": self._loading_spinner_css(),
            "PageHeader.jsx": self._page_header(),
            "PageHeader.module.css": self._page_header_css(),
            "index.js": self._index(),
        }
        files = {}
        for name, content in templates.items():
            # Explicit imports keep generated components compatible with both
            # automatic and classic JSX test transforms.
            if name.endswith(".jsx") and not content.startswith("import React"):
                content = "import React from 'react';\n" + content
            files[str(output_dir / name)] = content
        return files

    @staticmethod
    def _button() -> str:
        return '''import styles from './Button.module.css';

export default function Button({ variant = 'primary', type = 'button', className = '', children, ...props }) {
  return <button type={type} className={`${styles.button} ${styles[variant] || ''} ${className}`.trim()} {...props}>{children}</button>;
}
'''

    @staticmethod
    def _button_css() -> str:
        return '''.button { align-items: center; background: var(--color-primary); border: 1px solid transparent; border-radius: var(--radius-md); color: #fff; cursor: pointer; display: inline-flex; font: inherit; font-weight: 600; gap: .5rem; justify-content: center; min-height: 2.5rem; padding: .55rem 1rem; }
.button:hover:not(:disabled) { filter: brightness(1.08); }
.button:focus-visible { outline: 3px solid color-mix(in srgb, var(--color-primary) 35%, transparent); outline-offset: 2px; }
.button:disabled { cursor: not-allowed; opacity: .6; }
.secondary { background: var(--color-surface); border-color: var(--color-border); color: var(--color-text); }
.danger { background: var(--color-danger); }
.ghost { background: transparent; color: var(--color-primary); }
'''

    @staticmethod
    def _card() -> str:
        return '''import styles from './Card.module.css';

export default function Card({ as: Element = 'section', className = '', children, ...props }) {
  return <Element className={`${styles.card} ${className}`.trim()} {...props}>{children}</Element>;
}
'''

    @staticmethod
    def _card_css() -> str:
        return '''.card { background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-md); box-shadow: var(--shadow-sm); padding: 1.5rem; }
'''

    @staticmethod
    def _data_table() -> str:
        return '''import styles from './DataTable.module.css';
import EmptyState from './EmptyState';

export default function DataTable({ columns = [], rows = [], getRowId = (row) => row.id, emptyMessage = 'No records found.', renderActions }) {
  if (!rows.length) return <EmptyState message={emptyMessage} />;
  return <div className={styles.wrap}><table className={styles.table}><thead><tr>{renderActions && <th scope="col">Actions</th>}{columns.map((column) => <th key={column.key} scope="col">{column.label}</th>)}</tr></thead><tbody>{rows.map((row, index) => <tr key={getRowId(row) ?? index}>{renderActions && <td>{renderActions(row)}</td>}{columns.map((column) => <td key={column.key}>{column.render ? column.render(row) : (row[column.key] ?? '')}</td>)}</tr>)}</tbody></table></div>;
}
'''

    @staticmethod
    def _data_table_css() -> str:
        return '''.wrap { background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-md); overflow-x: auto; }
.table { border-collapse: collapse; min-width: 100%; width: 100%; }
.table th, .table td { border-bottom: 1px solid var(--color-border); padding: .875rem 1rem; text-align: left; vertical-align: top; }
.table th { background: var(--color-surface-muted); color: var(--color-text-muted); font-size: .8rem; letter-spacing: .04em; text-transform: uppercase; }
.table tr:last-child td { border-bottom: 0; }
'''

    @staticmethod
    def _empty_state() -> str:
        return '''export default function EmptyState({ title = 'Nothing here yet', message = 'No records found.', action = null }) {
  return <section role="status" style={{ padding: '2rem', textAlign: 'center' }}><h2>{title}</h2><p>{message}</p>{action}</section>;
}
'''

    @staticmethod
    def _error_boundary() -> str:
        return '''import { Component } from 'react';

export default class ErrorBoundary extends Component {
  state = { error: null };
  static getDerivedStateFromError(error) { return { error }; }
  componentDidCatch(error, info) { console.error('Application error:', error, info); }
  render() { if (this.state.error) return <main role="alert"><h1>Something went wrong</h1><p>Please refresh the page and try again.</p></main>; return this.props.children; }
}
'''

    @staticmethod
    def _error_message() -> str:
        return '''export default function ErrorMessage({ error, title = 'Unable to complete the request.' }) {
  if (!error) return null;
  return <div role="alert" style={{ background: '#fef2f2', borderRadius: '.5rem', color: '#b91c1c', margin: '1rem 0', padding: '1rem' }}><strong>{title}</strong><div>{error.message || error}</div></div>;
}
'''

    @staticmethod
    def _form_field() -> str:
        return '''import styles from './FormField.module.css';

export default function FormField({ label, name, type = 'text', value, onChange, required = false, disabled = false, options = [], placeholder = '', error = '', rows = 4 }) {
  const id = `field-${name}`;
  const describedBy = error ? `${id}-error` : undefined;
  if (type === 'checkbox') return <div className={styles.formGroup}><label className={styles.checkboxLabel}><input type="checkbox" name={name} checked={Boolean(value)} onChange={onChange} disabled={disabled} />{label}</label>{error && <span id={describedBy} className={styles.error} role="alert">{error}</span>}</div>;
  const control = type === 'select' ? <select id={id} name={name} value={value || ''} onChange={onChange} disabled={disabled} className={styles.select} aria-describedby={describedBy}><option value="">Select...</option>{options.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select> : type === 'textarea' ? <textarea id={id} name={name} value={value || ''} onChange={onChange} disabled={disabled} rows={rows} placeholder={placeholder} className={styles.textarea} aria-describedby={describedBy} /> : <input id={id} type={type} name={name} value={value || ''} onChange={onChange} required={required} disabled={disabled} placeholder={placeholder} className={styles.input} aria-describedby={describedBy} />;
  return <div className={styles.formGroup}><label htmlFor={id} className={styles.label}>{label}{required && ' *'}</label>{control}{error && <span id={describedBy} className={styles.error} role="alert">{error}</span>}</div>;
}
'''

    @staticmethod
    def _form_field_css() -> str:
        return '''.formGroup { margin-bottom: 1rem; }.label { display: block; font-weight: 600; margin-bottom: .4rem; }.input, .select, .textarea { background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-sm); color: var(--color-text); font: inherit; padding: .65rem .75rem; width: 100%; }.textarea { resize: vertical; }.input:focus, .select:focus, .textarea:focus { border-color: var(--color-primary); outline: 2px solid color-mix(in srgb, var(--color-primary) 20%, transparent); }.checkboxLabel { align-items: center; display: flex; font-weight: 600; gap: .5rem; }.error { color: var(--color-danger); display: block; font-size: .875rem; margin-top: .3rem; }
'''

    @staticmethod
    def _info_field() -> str:
        return '''export default function InfoField({ label, value }) { return <div style={{ borderBottom: '1px solid var(--color-border)', display: 'grid', gap: '.5rem', gridTemplateColumns: 'minmax(10rem, 30%) 1fr', padding: '.75rem 0' }}><strong>{label}</strong><span>{value ?? '—'}</span></div>; }
'''

    @staticmethod
    def _loading_spinner() -> str:
        return '''import styles from './LoadingSpinner.module.css';
export default function LoadingSpinner({ label = 'Loading...' }) { return <div className={styles.spinner} role="status" aria-live="polite"><span className={styles.indicator} aria-hidden="true" />{label}<span className={styles.srOnly}>Please wait</span></div>; }
'''

    @staticmethod
    def _loading_spinner_css() -> str:
        return '''.spinner { align-items: center; color: var(--color-text-muted); display: flex; gap: .65rem; justify-content: center; min-height: 7rem; }.indicator { animation: spin .7s linear infinite; border: 3px solid var(--color-border); border-radius: 50%; border-top-color: var(--color-primary); height: 1.25rem; width: 1.25rem; }@keyframes spin { to { transform: rotate(360deg); } }.srOnly { height: 1px; margin: -1px; overflow: hidden; position: absolute; width: 1px; clip: rect(0, 0, 0, 0); }
'''

    @staticmethod
    def _page_header() -> str:
        return '''import styles from './PageHeader.module.css';
export default function PageHeader({ title, description, action }) { return <header className={styles.header}><div><h1>{title}</h1>{description && <p>{description}</p>}</div>{action && <div className={styles.action}>{action}</div>}</header>; }
'''

    @staticmethod
    def _page_header_css() -> str:
        return '''.header { align-items: flex-start; display: flex; gap: 1rem; justify-content: space-between; margin-bottom: 1.5rem; }.header h1 { font-size: clamp(1.5rem, 3vw, 2rem); margin: 0; }.header p { color: var(--color-text-muted); margin: .35rem 0 0; }.action { flex: 0 0 auto; }@media (max-width: 640px) { .header { flex-direction: column; } }
'''

    @staticmethod
    def _index() -> str:
        return '''export { default as Button } from './Button';
export { default as Card } from './Card';
export { default as DataTable } from './DataTable';
export { default as EmptyState } from './EmptyState';
export { default as ErrorBoundary } from './ErrorBoundary';
export { default as ErrorMessage } from './ErrorMessage';
export { default as FormField } from './FormField';
export { default as InfoField } from './InfoField';
export { default as LoadingSpinner } from './LoadingSpinner';
export { default as PageHeader } from './PageHeader';
'''
