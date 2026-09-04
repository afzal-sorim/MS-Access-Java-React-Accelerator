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
export default function Access2JavaLogo({ size = 'md', compact = false, header = false }) {
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

  if (header) {
    return (
      <span style={{
        display: 'block',
        width: '220px',
        height: '40px',
        overflow: 'hidden',
        position: 'relative',
      }}>
        <img
          src="/access2java-logo.png"
          alt="access2Java"
          style={{
            position: 'absolute',
            width: '324px',
            maxWidth: 'none',
            height: 'auto',
            left: '-34px',
            top: '-9px',
          }}
        />
      </span>
    );
  }

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
        viewBox="0 0 96 90"
        width={iconW}
        height={c.h}
        style={{ display: 'block', flexShrink: 0, marginRight: c.gap }}
      >
        {/* Right Database Cylinder Stack (Behind) */}
        <rect x="49" y="16" width="42" height="56" fill="white" />
        <ellipse cx="70" cy="16" rx="21" ry="7.5" fill="white" stroke="#A4262C" strokeWidth="4" />
        <line x1="91" y1="16" x2="91" y2="72" stroke="#A4262C" strokeWidth="4" strokeLinecap="round" />
        <line x1="49" y1="16" x2="49" y2="72" stroke="#A4262C" strokeWidth="4" strokeLinecap="round" />
        <path d="M 49 72 C 49 77, 58 80.5, 70 80.5 C 82 80.5, 91 77, 91 72" fill="white" stroke="#A4262C" strokeWidth="4" strokeLinejoin="round" />
        <path d="M 49 35 C 49 39.5, 58 43, 70 43 C 82 43, 91 39.5, 91 35" fill="none" stroke="#A4262C" strokeWidth="4" />
        <path d="M 49 53 C 49 57.5, 58 61, 70 61 C 82 61, 91 57.5, 91 53" fill="none" stroke="#A4262C" strokeWidth="4" />

        {/* Left Red Angled Perspective Flap (Front) */}
        <path d="M 4 15 L 56 3 L 56 87 L 4 75 Z" fill="#A4262C" />
        <text x="30" y="58" fontFamily="'Arial Black', 'Arial', sans-serif" fontSize="44" fontWeight="900" fill="white" textAnchor="middle">A</text>
      </svg>


      {!compact && (
        <>
          {/* ══════════════════════════════════════════════════
              2. WORDMARK — HTML text, alignItems:baseline
              Guarantees perfect cross-browser baseline alignment
          ══════════════════════════════════════════════════ */}
          <div style={{
            display: 'inline-flex',
            alignItems: 'baseline',
            fontFamily: 'Arial, "Helvetica Neue", Helvetica, sans-serif',
            marginRight: c.gap,
            whiteSpace: 'nowrap',
            animation: 'fadeIn 0.2s ease-out'
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
            style={{ display: 'block', flexShrink: 0, overflow: 'visible', animation: 'fadeIn 0.2s ease-out' }}
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
        </>
      )}

    </div>
  );
}
