import React from 'react';

/**
 * Access2JavaLogo — matches the reference image exactly.
 *
 * Key visual detail from the reference:
 *  - The database cylinders OVERLAP the right edge of the red "A" square
 *    (the icon is one unified shape, not two separate parts)
 *  - The "access" text sits very close to the icon with minimal gap
 *  - "2" is visibly larger and orange
 *  - "Java" is the same size as "access", navy blue
 *  - Java cup is right next to "Java" with minimal gap
 *
 * size: 'sm' | 'md' | 'lg'
 */
export default function Access2JavaLogo({ size = 'md' }) {
  const cfg = {
    //           iconH  textSize   numSize   textGap
    sm: { h: 38, t: '1.5rem',  n: '1.8rem',  gap: '2px' },
    md: { h: 52, t: '2.1rem',  n: '2.55rem', gap: '3px' },
    lg: { h: 66, t: '2.65rem', n: '3.2rem',  gap: '4px' },
  };
  const c = cfg[size] || cfg.md;

  // The Access icon SVG is 96 wide × 90 tall (natural viewBox)
  // Cylinders extend from x=40 to x=96, overlapping the red square (x=0–62)
  const iconW = c.h;

  const cupH  = c.h;
  const cupW  = cupH;

  return (
    <div style={{
      display: 'inline-flex',
      alignItems: 'center',
      gap: 0,         // gaps are controlled per-element below
      lineHeight: 1,
      userSelect: 'none',
    }}>

      {/* ══════════════════════════════════════════════════
          1. MS ACCESS ICON  — modern, clean, flat-design:
          - Deep professional red geometric "A" panel on the left
          - White stacked database cylinder perfectly centered on the right
          - Panel overlaps the cylinder exactly like the original concept
      ══════════════════════════════════════════════════ */}
      <svg
        viewBox="0 0 24 24"
        width={iconW}
        height={c.h}
        style={{ display: 'block', flexShrink: 0, marginRight: c.gap }}
      >
        <path fill="#a4373a" d="M12,5.5 C16.4,5.5 20,6.5 20,7.8 V16.2 C20,17.5 16.4,18.5 12,18.5 V5.5 Z"/>
        <path fill="#ffffff" d="M12,6.5 C15.9,6.5 19,7.1 19,7.8 C19,8.5 15.9,9.1 12,9.1 C8.1,9.1 5,8.5 5,7.8 C5,7.1 8.1,6.5 12,6.5 Z M12,9.8 C15.9,9.8 19,10.4 19,11.1 C19,11.8 15.9,12.4 12,12.4 C8.1,12.4 5,11.8 5,11.1 C5,10.4 8.1,9.8 12,9.8 Z M12,13.1 C15.9,13.1 19,13.7 19,14.4 C19,15.1 15.9,15.7 12,15.7 C8.1,15.7 5,15.1 5,14.4 C5,13.7 8.1,13.1 12,13.1 Z"/>
        <path fill="#a4373a" d="M11.5,4L2.5,5.8V18.2L11.5,20V4Z"/>
        <path fill="#ffffff" d="M8.3,16L7.4,12.5H5.8L4.9,16H3.6L6,8.2H7.2L9.6,16H8.3ZM6,11.5H7.1L6.6,9.1L6,11.5Z"/>
      </svg>


      {/* ══════════════════════════════════════════════════
          2. WORDMARK — HTML text, alignItems:baseline
          Guarantees perfect cross-browser baseline alignment
      ══════════════════════════════════════════════════ */}
      <div style={{
        display: 'inline-flex',
        alignItems: 'baseline',
        fontFamily: 'Arial, "Helvetica Neue", Helvetica, sans-serif',
        marginRight: c.gap,
      }}>
        {/* "access" — dark crimson red */}
        <span style={{
          color: '#B32025',
          fontSize: c.t,
          fontWeight: '700',
          letterSpacing: '-0.5px',
          lineHeight: 1,
        }}>access</span>

        {/* "2" — orange, visibly larger */}
        <span style={{
          color: '#E67E22',
          fontSize: c.n,
          fontWeight: '900',
          fontFamily: '"Arial Black", Arial, sans-serif',
          lineHeight: 1,
          letterSpacing: 0,
        }}>2</span>

        {/* "Java" — navy blue */}
        <span style={{
          color: '#1B5696',
          fontSize: c.t,
          fontWeight: '700',
          letterSpacing: '-0.5px',
          lineHeight: 1,
        }}>Java</span>
      </div>

      {/* ══════════════════════════════════════════════════
          3. JAVA COFFEE CUP
          Steam wisps above, classic cup body + handle, saucer
      ══════════════════════════════════════════════════ */}
      <svg
        viewBox="0 0 128 128"
        width={cupW}
        height={cupH}
        style={{ display: 'block', flexShrink: 0, overflow: 'visible' }}
      >
        <path fill="#0074BD" d="M47.617 98.12s-4.767 2.774 3.397 3.71c9.892 1.13 14.947.968 25.845-1.092 0 0 2.871 1.795 6.873 3.351-24.439 10.47-55.308-.607-36.115-5.969zm-2.988-13.665s-5.348 3.959 2.823 4.805c10.567 1.091 18.91 1.18 33.354-1.6 0 0 1.993 2.025 5.132 3.131-29.542 8.64-62.446.68-41.309-6.336z"/>
        <path fill="#EA2D2E" d="M69.802 61.271c6.025 6.935-1.58 13.17-1.58 13.17s15.289-7.891 8.269-17.777c-6.559-9.215-11.587-13.792 15.635-29.58 0 .001-42.731 10.67-22.324 34.187z"/>
        <path fill="#0074BD" d="M102.123 108.229s3.529 2.91-3.888 5.159c-14.102 4.272-58.706 5.56-71.094.171-4.451-1.938 3.899-4.625 6.526-5.192 2.739-.593 4.303-.485 4.303-.485-4.953-3.487-32.013 6.85-13.743 9.815 49.821 8.076 90.817-3.637 77.896-9.468zM49.912 70.294s-22.686 5.389-8.033 7.348c6.188.828 18.518.638 30.011-.326 9.39-.789 18.813-2.474 18.813-2.474s-3.308 1.419-5.704 3.053c-23.042 6.061-67.544 3.238-54.731-2.958 10.832-5.239 19.644-4.643 19.644-4.643zm40.697 22.747c23.421-12.167 12.591-23.86 5.032-22.285-1.848.385-2.677.72-2.677.72s.688-1.079 2-1.543c14.953-5.255 26.451 15.503-4.823 23.725 0-.002.359-.327.468-.617z"/>
        <path fill="#EA2D2E" d="M76.491 1.587S89.459 14.563 64.188 34.51c-20.266 16.006-4.621 25.13-.007 35.559-11.831-10.673-20.509-20.07-14.688-28.815C58.041 28.42 81.722 22.195 76.491 1.587z"/>
        <path fill="#0074BD" d="M52.214 126.021c22.476 1.437 57-.8 57.817-11.436 0 0-1.571 4.032-18.577 7.231-19.186 3.612-42.854 3.191-56.887.874 0 .001 2.875 2.381 17.647 3.331z"/>
      </svg>

    </div>
  );
}
