import { useEffect, useId, useRef, useState } from 'react';
import { geocode } from '../api';
import type { Place } from '../types';

interface Props {
  label: string;
  value: Place | string;
  onChange: (value: Place | string) => void;
  placeholder?: string;
}

/** Text input with debounced place autocomplete. Free text is geocoded server-side on submit. */
export function PlaceInput({ label, value, onChange, placeholder }: Props) {
  const id = useId();
  const text = typeof value === 'string' ? value : value.label;
  const [results, setResults] = useState<Place[]>([]);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const blurTimer = useRef<number | undefined>(undefined);

  const searchable = typeof value === 'string' && value.trim().length >= 3;
  const options = searchable ? results : [];

  useEffect(() => {
    if (typeof value !== 'string' || value.trim().length < 3) return;
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      geocode(value, controller.signal)
        .then((places) => {
          setResults(places);
          setActive(-1);
        })
        .catch(() => undefined);
    }, 300);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [value]);

  const choose = (place: Place) => {
    onChange(place);
    setOpen(false);
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (!open || options.length === 0) return;
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActive((a) => (a + 1) % options.length);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActive((a) => (a <= 0 ? options.length - 1 : a - 1));
    } else if (e.key === 'Enter' && active >= 0) {
      e.preventDefault();
      choose(options[active]);
    } else if (e.key === 'Escape') {
      setOpen(false);
    }
  };

  return (
    <div className="field place-input">
      <label htmlFor={id}>{label}</label>
      <input
        id={id}
        type="text"
        autoComplete="off"
        value={text}
        placeholder={placeholder}
        onChange={(e) => {
          onChange(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => {
          blurTimer.current = window.setTimeout(() => setOpen(false), 150);
        }}
        onKeyDown={onKeyDown}
        role="combobox"
        aria-expanded={open && options.length > 0}
        aria-controls={`${id}-list`}
        required
      />
      {typeof value !== 'string' && <span className="place-check" title="Location confirmed">✓</span>}
      {open && options.length > 0 && (
        <ul className="suggestions" id={`${id}-list`} role="listbox">
          {options.map((place, i) => (
            <li
              key={`${place.lat},${place.lon},${i}`}
              role="option"
              aria-selected={i === active}
              className={i === active ? 'active' : ''}
              onMouseDown={(e) => {
                e.preventDefault();
                clearTimeout(blurTimer.current);
                choose(place);
              }}
            >
              {place.label}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
