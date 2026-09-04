import React from 'react';
import { Database, FileText, Layout, PlaySquare, Code } from 'lucide-react';

const DependenciesDiagram = ({ progress }) => {
    // We mock the diagram nodes using flexbox
    
    const tables = progress.tables?.count || 0;
    const queries = progress.queries?.count || 0;
    const forms = progress.forms?.count || 0;
    const reports = progress.reports?.count || 0;
    const modules = progress.vba?.count || 0;
    
    const totalDeps = 142; // Mock
    const activeDeps = 128; // Mock
    const circularDeps = 1; // Mock
    const orphanedDeps = 3; // Mock

    return (
        <div className="card" style={{ padding: '1.5rem', flex: 1.5, minWidth: '400px', display: 'flex', flexDirection: 'column' }}>
            <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '0.25rem' }}>Dependencies Overview</h3>
            <p style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', marginBottom: '1.5rem' }}>Overview of object dependencies</p>
            
            <div style={{ display: 'flex', flex: 1 }}>
                {/* Mock Diagram Area */}
                <div style={{ flex: 1, position: 'relative', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    {/* Very basic manual graph using absolute positioning and SVG lines would be complex. Let's use a simpler flex layout mimicking the design */}
                    
                    <div style={{ position: 'relative', width: '280px', height: '200px' }}>
                        {/* Center - Tables */}
                        <div style={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%)', zIndex: 10,
                            width: '80px', height: '80px', borderRadius: '50%', backgroundColor: '#8b5cf6', color: 'white',
                            display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', boxShadow: '0 4px 6px rgba(139, 92, 246, 0.3)'
                        }}>
                            <span style={{ fontSize: '0.75rem', fontWeight: 500 }}>Tables</span>
                            <span style={{ fontSize: '1.25rem', fontWeight: 700 }}>{tables}</span>
                        </div>
                        
                        {/* Top - Queries */}
                        <div style={{ position: 'absolute', top: '10px', left: '50%', transform: 'translateX(-50%)', zIndex: 10,
                            padding: '0.5rem 1rem', borderRadius: '8px', border: '1px solid #10b981', backgroundColor: 'white',
                            display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#10b981'
                        }}>
                            <Database size={16} />
                            <div>
                                <div style={{ fontSize: '0.625rem', fontWeight: 600 }}>Queries</div>
                                <div style={{ fontSize: '0.875rem', fontWeight: 700 }}>{queries}</div>
                            </div>
                        </div>

                        {/* Bottom - Reports */}
                        <div style={{ position: 'absolute', bottom: '10px', left: '50%', transform: 'translateX(-50%)', zIndex: 10,
                            padding: '0.5rem 1rem', borderRadius: '8px', border: '1px solid #3b82f6', backgroundColor: 'white',
                            display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#3b82f6'
                        }}>
                            <FileText size={16} />
                            <div>
                                <div style={{ fontSize: '0.625rem', fontWeight: 600 }}>Reports</div>
                                <div style={{ fontSize: '0.875rem', fontWeight: 700 }}>{reports}</div>
                            </div>
                        </div>

                        {/* Left - Modules */}
                        <div style={{ position: 'absolute', top: '50%', left: '10px', transform: 'translateY(-50%)', zIndex: 10,
                            padding: '0.5rem 1rem', borderRadius: '8px', border: '1px solid #8b5cf6', backgroundColor: 'white',
                            display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#8b5cf6'
                        }}>
                            <Code size={16} />
                            <div>
                                <div style={{ fontSize: '0.625rem', fontWeight: 600 }}>Modules</div>
                                <div style={{ fontSize: '0.875rem', fontWeight: 700 }}>{modules}</div>
                            </div>
                        </div>

                        {/* Right - Forms */}
                        <div style={{ position: 'absolute', top: '50%', right: '10px', transform: 'translateY(-50%)', zIndex: 10,
                            padding: '0.5rem 1rem', borderRadius: '8px', border: '1px solid #f59e0b', backgroundColor: 'white',
                            display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#f59e0b'
                        }}>
                            <Layout size={16} />
                            <div>
                                <div style={{ fontSize: '0.625rem', fontWeight: 600 }}>Forms</div>
                                <div style={{ fontSize: '0.875rem', fontWeight: 700 }}>{forms}</div>
                            </div>
                        </div>
                        
                        {/* Connecting Lines (CSS borders) */}
                        <div style={{ position: 'absolute', top: '40px', bottom: '40px', left: '50%', width: '1px', backgroundColor: '#e2e8f0', transform: 'translateX(-50%)', zIndex: 1 }}></div>
                        <div style={{ position: 'absolute', left: '60px', right: '60px', top: '50%', height: '1px', backgroundColor: '#e2e8f0', transform: 'translateY(-50%)', zIndex: 1 }}></div>
                    </div>
                </div>
                
                {/* Stats Panel */}
                <div style={{ width: '140px', display: 'flex', flexDirection: 'column', gap: '1rem', borderLeft: '1px solid var(--color-border)', paddingLeft: '1.5rem', justifyContent: 'center' }}>
                    <div style={{ textAlign: 'center' }}>
                        <div style={{ fontSize: '0.625rem', color: 'var(--color-text-muted)' }}>Total Dependencies</div>
                        <div style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--color-navy)' }}>{totalDeps}</div>
                    </div>
                    <div style={{ textAlign: 'center' }}>
                        <div style={{ fontSize: '0.625rem', color: 'var(--color-text-muted)' }}>Active Dependencies</div>
                        <div style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--color-navy)' }}>{activeDeps}</div>
                    </div>
                    <div style={{ textAlign: 'center' }}>
                        <div style={{ fontSize: '0.625rem', color: 'var(--color-text-muted)' }}>Circular Dependencies</div>
                        <div style={{ fontSize: '1.25rem', fontWeight: 700, color: '#ef4444' }}>{circularDeps}</div>
                    </div>
                    <div style={{ textAlign: 'center' }}>
                        <div style={{ fontSize: '0.625rem', color: 'var(--color-text-muted)' }}>Orphaned Objects</div>
                        <div style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--color-navy)' }}>{orphanedDeps}</div>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default DependenciesDiagram;
