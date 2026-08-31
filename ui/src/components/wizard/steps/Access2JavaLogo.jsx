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
  const iconW = c.h * (96 / 90);

  // Java cup SVG is 80 wide × 100 tall
  const cupH  = c.h * 1.1;
  const cupW  = cupH * (80 / 100);

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
        viewBox="0 0 92 90"
        width={iconW}
        height={c.h}
        style={{ display: 'block', flexShrink: 0, marginRight: c.gap }}
      >
        {/* ── Database Cylinder (Behind) ── */}
        <rect x="39" y="24" width="48" height="42" fill="white" />
        
        {/* Bottom cap (perfect bezier half-ellipse) */}
        <path d="M 39 66 C 39 70.14, 49.75 73.5, 63 73.5 C 76.25 73.5, 87 70.14, 87 66" fill="white" stroke="#B32025" strokeWidth="3.5" strokeLinejoin="round" />
        
        {/* Side outlines */}
        <line x1="39" y1="24" x2="39" y2="66" stroke="#B32025" strokeWidth="3.5" strokeLinecap="round" />
        <line x1="87" y1="24" x2="87" y2="66" stroke="#B32025" strokeWidth="3.5" strokeLinecap="round" />

        {/* Dividers */}
        <path d="M 39 38 C 39 42.14, 49.75 45.5, 63 45.5 C 76.25 45.5, 87 42.14, 87 38" fill="none" stroke="#B32025" strokeWidth="3.5" />
        <path d="M 39 52 C 39 56.14, 49.75 59.5, 63 59.5 C 76.25 59.5, 87 56.14, 87 52" fill="none" stroke="#B32025" strokeWidth="3.5" />

        {/* Top cap (full ellipse) */}
        <ellipse cx="63" cy="24" rx="24" ry="7.5" fill="white" stroke="#B32025" strokeWidth="3.5" />

        {/* ── Red geometric "A" panel (Front) ── */}
        {/* This clean flat panel overlaps the cylinder, preserving the concept */}
        <rect x="4" y="10" width="45" height="70" rx="7" fill="#B32025" />
        <text
          x="26.5" y="58"
          fontFamily="'Arial Black', 'Arial', sans-serif"
          fontSize="46"
          fontWeight="900"
          fill="white"
          textAnchor="middle"
        >A</text>
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
        viewBox="0 0 80 100"
        width={cupW}
        height={cupH}
        style={{ display: 'block', flexShrink: 0, overflow: 'visible' }}
      >
        {/* Steam wisps — 3 organic wavy lines */}
        <path d="M18,30 C14,22 22,14 18,6 C14,-1 20,-5 20,-5"
          fill="none" stroke="#E57C22" strokeWidth="3.8" strokeLinecap="round"/>
        <path d="M36,28 C32,19 40,11 36,3 C32,-5 38,-9 38,-9"
          fill="none" stroke="#E57C22" strokeWidth="3.8" strokeLinecap="round"/>
        <path d="M54,30 C50,22 58,14 54,6 C50,-1 56,-5 56,-5"
          fill="none" stroke="#E57C22" strokeWidth="3.8" strokeLinecap="round"/>

        {/* Cup body */}
        <path
          d="M8,34 L13,82 Q13,88 36,88 Q59,88 59,82 L64,34 Z"
          fill="white"
          stroke="#1B5696"
          strokeWidth="4.5"
          strokeLinejoin="round"
          strokeLinecap="round"
        />

        {/* Handle */}
        <path
          d="M62,47 Q78,47 78,60 Q78,73 62,73"
          fill="none"
          stroke="#1B5696"
          strokeWidth="4.5"
          strokeLinecap="round"
        />

        {/* Saucer outer */}
        <ellipse cx="36" cy="89" rx="35" ry="7" fill="none" stroke="#1B5696" strokeWidth="3.5"/>
        {/* Saucer inner ring */}
        <ellipse cx="36" cy="89" rx="14" ry="2.8" fill="none" stroke="#1B5696" strokeWidth="2"/>
      </svg>

    </div>
  );
}
