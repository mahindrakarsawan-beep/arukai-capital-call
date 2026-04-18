"use client";

/**
 * AuditFilterBar — filter controls for the global audit ledger.
 * Spec §B2 / §1.7 copy:
 *  - Filter by actor (text input)
 *  - Filter by action (text input — backend accepts action string)
 *  - From date / To date (date pickers)
 *  - "Apply filters" primary button
 *  - "Clear" ghost button
 *
 * Typography: DM Sans (interface font) throughout — labels, inputs, buttons.
 * No Cormorant in filter controls (§9.1).
 */

import React, { useState } from "react";

export interface AuditFilterValues {
  actor_id: string;
  action: string;
  from_date: string;
  to_date: string;
}

interface AuditFilterBarProps {
  onApply: (filters: AuditFilterValues) => void;
  onClear: () => void;
  initialValues?: AuditFilterValues;
}

const EMPTY: AuditFilterValues = {
  actor_id: "",
  action: "",
  from_date: "",
  to_date: "",
};

export function AuditFilterBar({
  onApply,
  onClear,
  initialValues,
}: AuditFilterBarProps) {
  const [values, setValues] = useState<AuditFilterValues>(
    initialValues ?? EMPTY
  );

  function set(key: keyof AuditFilterValues, val: string) {
    setValues((v) => ({ ...v, [key]: val }));
  }

  function handleClear() {
    setValues(EMPTY);
    onClear();
  }

  const inputClass =
    "w-full rounded-lg border border-border-hairline bg-bg-bone px-3 py-2.5 font-interface text-sm text-fg-obsidian placeholder:text-fg-muted focus:outline-none focus:border-fg-slate focus:ring-1 focus:ring-fg-slate transition-colors duration-fast appearance-none";

  const labelClass = "block font-interface text-xs font-medium uppercase tracking-wider text-fg-muted mb-1";

  return (
    <div className="rounded-xl border border-border-hairline bg-bg-parchment p-6">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {/* Filter by actor */}
        <div>
          <label htmlFor="audit-filter-actor" className={labelClass}>
            Filter by actor
          </label>
          <input
            id="audit-filter-actor"
            type="text"
            className={inputClass}
            value={values.actor_id}
            onChange={(e) => set("actor_id", e.target.value)}
            aria-label="Filter by actor"
          />
        </div>

        {/* Filter by action */}
        <div>
          <label htmlFor="audit-filter-action" className={labelClass}>
            Filter by action
          </label>
          <input
            id="audit-filter-action"
            type="text"
            className={inputClass}
            value={values.action}
            onChange={(e) => set("action", e.target.value)}
            aria-label="Filter by action"
          />
        </div>

        {/* From date */}
        <div>
          <label htmlFor="audit-filter-from" className={labelClass}>
            From
          </label>
          <input
            id="audit-filter-from"
            type="date"
            className={inputClass}
            value={values.from_date}
            onChange={(e) => set("from_date", e.target.value)}
            aria-label="From"
          />
        </div>

        {/* To date */}
        <div>
          <label htmlFor="audit-filter-to" className={labelClass}>
            To
          </label>
          <input
            id="audit-filter-to"
            type="date"
            className={inputClass}
            value={values.to_date}
            onChange={(e) => set("to_date", e.target.value)}
            aria-label="To"
          />
        </div>
      </div>

      {/* Action row */}
      <div className="mt-4 flex items-center gap-3">
        <button
          type="button"
          onClick={() => onApply(values)}
          className="font-interface text-sm font-semibold bg-fg-obsidian text-bg-bone px-4 py-2 rounded transition-opacity duration-fast hover:opacity-80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-fg-slate"
        >
          Apply filters
        </button>
        <button
          type="button"
          onClick={handleClear}
          className="font-interface text-sm text-fg-slate hover:text-fg-obsidian border border-border-hairline px-4 py-2 rounded transition-colors duration-fast focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-fg-slate"
        >
          Clear
        </button>
      </div>
    </div>
  );
}
