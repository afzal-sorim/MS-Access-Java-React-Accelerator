import React, { memo, useEffect, useRef, useState } from 'react';
import './Access2JavaLoader.css';

export default function Access2JavaLoader({ 
  isVisible = true, 
  databaseName = 'Database.accdb',
  fileSize = '0.00 MB',
  scannedData = null,
  isComplete = false,
  onDurationRecorded = null
}) {
  if (!isVisible) return null;

  const [percentage, setPercentage] = useState(12);
  const [currentStepIdx, setCurrentStepIdx] = useState(0);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  const dynamicStages = [
    {
      label: `Reading database binary catalog (${databaseName} • ${fileSize})...`,
      targetPct: 20
    },
    {
      label: `Extracting relational tables & schema definitions...`,
      targetPct: 40
    },
    {
      label: `Parsing SQL queries & join expressions...`,
      targetPct: 60
    },
    {
      label: `Analyzing UI forms & report layouts...`,
      targetPct: 75
    },
    {
      label: `Inspecting VBA business logic & procedures...`,
      targetPct: 88
    },
    {
      label: `Building dependency graph & finalizing discovery...`,
      targetPct: 100
    }
  ];

  const elapsedSecondsRef = useRef(0);

  useEffect(() => {
    elapsedSecondsRef.current = elapsedSeconds;
  }, [elapsedSeconds]);

  const onDurationRecordedRef = useRef(onDurationRecorded);
  useEffect(() => {
    onDurationRecordedRef.current = onDurationRecorded;
  }, [onDurationRecorded]);

  // When loader unmounts, accurately pass elapsed loader time once
  useEffect(() => {
    return () => {
      if (typeof onDurationRecordedRef.current === 'function' && elapsedSecondsRef.current > 0) {
        const secs = elapsedSecondsRef.current;
        const h = String(Math.floor(secs / 3600)).padStart(2, '0');
        const m = String(Math.floor((secs % 3600) / 60)).padStart(2, '0');
        const s = String(secs % 60).padStart(2, '0');
        onDurationRecordedRef.current(`${h}:${m}:${s}`);
      }
    };
  }, []);

  useEffect(() => {
    const startTime = Date.now();
    const interval = setInterval(() => {
      const elapsedMs = Date.now() - startTime;
      const elapsedSec = Math.floor(elapsedMs / 1000);
      setElapsedSeconds(elapsedSec);

      if (isComplete) {
        setPercentage(100);
        setCurrentStepIdx(dynamicStages.length - 1);
      } else {
        // Dynamic continuous progression based strictly on elapsed timer
        // Smooth asymptotic curve that never reaches 100% prematurely (caps at 95% while scanning)
        const progressVal = 12 + 83 * (1 - Math.exp(-elapsedSec / 16));
        const newPct = Math.min(95, Math.round(progressVal));
        setPercentage(newPct);

        // Stages progress in real-time with the timer
        let stepIdx = 0;
        if (newPct >= 88) stepIdx = 5;
        else if (newPct >= 75) stepIdx = 4;
        else if (newPct >= 60) stepIdx = 3;
        else if (newPct >= 40) stepIdx = 2;
        else if (newPct >= 20) stepIdx = 1;
        else stepIdx = 0;

        setCurrentStepIdx(stepIdx);
      }
    }, 100);

    return () => clearInterval(interval);
  }, [isComplete, dynamicStages.length]);

  const currentStage = dynamicStages[currentStepIdx] || dynamicStages[0];

  const formatTimer = (secs) => {
    const mm = String(Math.floor(secs / 60)).padStart(2, '0');
    const ss = String(secs % 60).padStart(2, '0');
    return `${mm}:${ss}`;
  };

  return (
    <div className="a2j-loader-overlay">
      <div className="a2j-loader-container">
        {/* Animated 3D Logo Rings */}
        <div className="a2j-loader-rings">
          <div className="a2j-loader-halo" />

          <svg width="140" height="140" viewBox="0 0 150 150" className="a2j-loader-ring-svg">
            <defs>
              <linearGradient id="a2jArcGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="#991B1B" />
                <stop offset="45%" stopColor="#D97706" />
                <stop offset="100%" stopColor="#3730A3" />
              </linearGradient>
            </defs>
            <circle cx="75" cy="75" r="60" fill="none" stroke="#eef1f6" strokeWidth="2.5" />
            <g className="a2j-loader-ring-outer">
              <circle
                cx="75" cy="75" r="60" fill="none"
                stroke="url(#a2jArcGradient)" strokeWidth="3.5" strokeLinecap="round"
                strokeDasharray="150 227"
              />
              <circle cx="75" cy="15" r="5.5" fill="#991B1B" />
            </g>
            <g className="a2j-loader-ring-inner" opacity={0.28}>
              <circle
                cx="75" cy="75" r="47" fill="none"
                stroke="#3730A3" strokeWidth="1.5" strokeDasharray="3 8"
              />
            </g>
          </svg>

          {/* Centered Java Teacup Icon (Exactly matching reference logo) */}
          <div className="a2j-loader-center-content" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <svg 
              width="44" 
              height="44" 
              viewBox="0 0 128 128" 
              style={{ 
                display: 'block', 
                overflow: 'visible',
                filter: 'drop-shadow(0 2px 6px rgba(55, 48, 163, 0.15))' 
              }}
            >
              {/* Saucer / Base Arcs (Java Blue) */}
              <path fill="#5382A1" d="M47.617 98.12s-4.767 2.774 3.397 3.71c9.892 1.13 14.947.968 25.845-1.092 0 0 2.871 1.795 6.873 3.351-24.439 10.47-55.308-.607-36.115-5.969zm-2.988-13.665s-5.348 3.959 2.823 4.805c10.567 1.091 18.91 1.18 33.354-1.6 0 0 1.993 2.025 5.132 3.131-29.542 8.64-62.446.68-41.309-6.336z"/>
              {/* Right Steam Flame (Java Orange) */}
              <path fill="#E76F00" d="M69.802 61.271c6.025 6.935-1.58 13.17-1.58 13.17s15.289-7.891 8.269-17.777c-6.559-9.215-11.587-13.792 15.635-29.58 0 .001-42.731 10.67-22.324 34.187z"/>
              {/* Cup Rim & Handle (Java Blue) */}
              <path fill="#5382A1" d="M102.123 108.229s3.529 2.91-3.888 5.159c-14.102 4.272-58.706 5.56-71.094.171-4.451-1.938 3.899-4.625 6.526-5.192 2.739-.593 4.303-.485 4.303-.485-4.953-3.487-32.013 6.85-13.743 9.815 49.821 8.076 90.817-3.637 77.896-9.468zM49.912 70.294s-22.686 5.389-8.033 7.348c6.188.828 18.518.638 30.011-.326 9.39-.789 18.813-2.474 18.813-2.474s-3.308 1.419-5.704 3.053c-23.042 6.061-67.544 3.238-54.731-2.958 10.832-5.239 19.644-4.643 19.644-4.643zm40.697 22.747c23.421-12.167 12.591-23.86 5.032-22.285-1.848.385-2.677.72-2.677.72s.688-1.079 2-1.543c14.953-5.255 26.451 15.503-4.823 23.725 0-.002.359-.327.468-.617z"/>
              {/* Main Left Steam Flame (Java Orange) */}
              <path fill="#E76F00" d="M76.491 1.587S89.459 14.563 64.188 34.51c-20.266 16.006-4.621 25.13-.007 35.559-11.831-10.673-20.509-20.07-14.688-28.815C58.041 28.42 81.722 22.195 76.491 1.587z"/>
              {/* Bottom Saucer Curve (Java Blue) */}
              <path fill="#5382A1" d="M52.214 126.021c22.476 1.437 57-.8 57.817-11.436 0 0-1.571 4.032-18.577 7.231-19.186 3.612-42.854 3.191-56.887.874 0 .001 2.875 2.381 17.647 3.331z"/>
            </svg>
          </div>
        </div>

        {/* Wordmark Title */}
        <div className="a2j-loader-wordmark">
          <div className="a2j-loader-title">
            <span className="a2j-loader-title-red">access</span>
            <span className="a2j-loader-title-orange">2</span>
            <span className="a2j-loader-title-indigo">Java</span>
          </div>
          <div className="a2j-loader-underline" />
          <div className="a2j-loader-tagline">MIGRATE. MODERNIZE. FUTURE-READY.</div>
        </div>

        {/* Dynamic Continuous Progress Bar with Live Percentage Counter */}
        <div className="a2j-loader-progress-section">
          <div className="a2j-loader-progress-labels">
            <span className="a2j-loader-stage-indicator">Stage {currentStepIdx + 1} of {dynamicStages.length}</span>
            <span className="a2j-loader-percentage-indicator">{percentage}%</span>
          </div>

          <div className="a2j-loader-progress-track">
            <div 
              className="a2j-loader-progress-fill" 
              style={{ width: `${percentage}%` }}
            >
              <div className="a2j-loader-progress-shimmer" />
            </div>
          </div>
        </div>

        {/* Dynamic Status Message */}
        <div className="a2j-loader-status-text">
          {currentStage.label}
        </div>

        {/* Elapsed Timer Pill */}
        <div className="a2j-loader-timer-pill">
          <span>⏱ {formatTimer(elapsedSeconds)}</span>
        </div>
      </div>
    </div>
  );
}
