import React, { useState, useRef } from 'react';
import axios from 'axios';
import { Upload, FileText, X, CheckCircle, AlertCircle, Download, Clock, BarChart2, ShieldCheck, FileCheck } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

const API_BASE = 'http://localhost:8000';

const App = () => {
  const [ay, setAy] = useState('2024-25');
  const [files, setFiles] = useState([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [results, setResults] = useState(null);
  const [error, setError] = useState(null);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef(null);

  const handleFileChange = (e) => {
    const selectedFiles = Array.from(e.target.files).filter(f => f.type === 'application/pdf');
    setFiles(prev => [...prev, ...selectedFiles]);
  };

  const removeFile = (index) => {
    setFiles(prev => prev.filter((_, i) => i !== index));
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    const droppedFiles = Array.from(e.dataTransfer.files).filter(f => f.type === 'application/pdf');
    setFiles(prev => [...prev, ...droppedFiles]);
  };

  const processStatements = async () => {
    if (files.length === 0) return;
    setIsProcessing(true);
    setError(null);
    setResults(null);

    const formData = new FormData();
    formData.append('ay', ay);
    files.forEach(file => formData.append('files', file));

    try {
      const response = await axios.post(`${API_BASE}/process`, formData);
      setResults(response.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'System Error: Validation failed or service unreachable.');
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div className="app-container">
      <header>
        <motion.div 
          initial={{ opacity: 0, scale: 0.8 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.5 }}
          style={{ display: 'flex', justifyContent: 'center', marginBottom: '1.5rem'}}
        >
          <div style={{ background: '#eff6ff', padding: '1rem', borderRadius: '20px', display: 'flex', alignItems: 'center', gap: '0.75rem', border: '1px solid #dbeafe'}}>
            <ShieldCheck color="#1e40af" size={24} />
            <span style={{ fontWeight: 700, color: '#1e40af', fontSize: '0.9rem', letterSpacing: '0.05em'}}>SECURE EXTRACTION ENGINE</span>
          </div>
        </motion.div>
        
        <motion.h1 
          initial={{ opacity: 0, y: -20 }} 
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
        >
          Universal <span style={{color: '#3b82f6'}}>Phaser</span>
        </motion.h1>
        <p className="subtitle">Truly universal, coordinate-aware bank statement parser</p>
      </header>

      <main>
        <div className="card">
          <div className="form-group">
            <label>ASSESSMENT YEAR (FY {ay.split('-')[0] ? parseInt(ay.split('-')[0])-1 : '0000'}-{ay.split('-')[0] || '0000'})</label>
            <input 
              type="text" 
              value={ay} 
              onChange={(e) => setAy(e.target.value)} 
              placeholder="Enter AY (e.g. 2024-25)"
            />
          </div>

          <motion.div 
            className={`upload-zone ${isDragging ? 'dragging' : ''}`}
            onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
            onDragLeave={() => setIsDragging(false)}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current.click()}
            whileHover={{ scale: 1.005 }}
            whileTap={{ scale: 0.995 }}
          >
            <input 
              type="file" 
              multiple 
              hidden 
              ref={fileInputRef} 
              onChange={handleFileChange}
              accept=".pdf"
            />
            <Upload className="upload-icon" />
            <h3 style={{fontSize: '1.25rem', color: '#1e293b', marginBottom: '0.5rem'}}>Select or Drag PDF Statements</h3>
            <p style={{color: '#94a3b8', fontSize: '0.95rem', fontWeight: 500}}>Multi-file selection supported</p>
          </motion.div>

          <AnimatePresence>
            {files.length > 0 && (
              <motion.div 
                className="file-list"
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                transition={{ duration: 0.3 }}
              >
                {files.map((file, idx) => (
                  <motion.div 
                    key={idx} 
                    className="file-item"
                    initial={{ x: -20, opacity: 0 }}
                    animate={{ x: 0, opacity: 1 }}
                    transition={{ delay: idx * 0.05 }}
                  >
                    <div className="file-info">
                      <div style={{ background: '#f0f9ff', padding: '0.5rem', borderRadius: '8px'}}>
                        <FileText size={20} color="#3b82f6" strokeWidth={2.5} />
                      </div>
                      <span className="file-name">{file.name}</span>
                    </div>
                    <X className="remove-btn" size={20} onClick={(e) => { e.stopPropagation(); removeFile(idx); }} />
                  </motion.div>
                ))}
              </motion.div>
            )}
          </AnimatePresence>

          <div style={{ marginTop: '2.5rem', display: 'flex', justifyContent: 'flex-end'}}>
            <button 
              className={`btn btn-primary ${isProcessing || files.length === 0 ? 'btn-disabled' : ''}`}
              disabled={isProcessing || files.length === 0}
              onClick={processStatements}
              style={{ width: '100%', maxWidth: '240px'}}
            >
              {isProcessing ? (
                <><span className="loader"></span> ANALYZING...</>
              ) : (
                <span style={{ display: 'flex', alignItems: 'center', gap: '0.75rem'}}>
                   <FileCheck size={20} /> START EXTRACTION
                </span>
              )}
            </button>
          </div>
        </div>

        <AnimatePresence>
          {error && (
            <motion.div 
              className="error-msg"
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
            >
              <AlertCircle size={22} style={{marginRight: '1rem', flexShrink: 0}} />
              <span>{error}</span>
            </motion.div>
          )}

          {results && (
            <motion.div 
              className="card"
              initial={{ y: 30, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              transition={{ type: 'spring', damping: 20 }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem'}}>
                <div>
                  <h2 style={{fontSize: '1.4rem', fontWeight: 800, color: '#1e293b'}}>Extraction Summary</h2>
                  <p style={{ fontSize: '0.9rem', color: '#94a3b8', fontWeight: 500}}>Job ID: {results.job_id.split('-')[0]}</p>
                </div>
                <div style={{fontSize: '0.9rem', fontWeight: 700, color: '#64748b', display: 'flex', gap: '2rem'}}>
                  <span style={{ display: 'flex', alignItems: 'center', gap: '0.5rem'}}><Clock size={16} /> {results.time_taken}S</span>
                  <span style={{ display: 'flex', alignItems: 'center', gap: '0.5rem'}}><BarChart2 size={16} /> {results.results.length} ACCOUNTS</span>
                </div>
              </div>

              <div style={{ overflowX: 'auto' }}>
                <table className="results-table">
                  <thead>
                    <tr>
                      <th>Account Detail</th>
                      <th>Volume</th>
                      <th>FY Activity</th>
                      <th style={{ textAlign: 'right' }}>Report</th>
                    </tr>
                  </thead>
                  <tbody>
                    {results.results.map((res, i) => (
                      <motion.tr 
                        key={i}
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.2 + i * 0.1 }}
                      >
                        <td>
                          <div style={{fontWeight: 700, fontSize: '1rem', color: '#1e293b'}}>{res.account_no}</div>
                          <div style={{fontSize: '0.85rem', color: '#94a3b8', fontWeight: 600}}>{res.bank}</div>
                        </td>
                        <td>
                          <span className="badge badge-success">{res.transaction_count} TXNS</span>
                        </td>
                        <td>
                          <div style={{color: '#059669', fontSize: '0.95rem', fontWeight: 700}}>+ ₹{res.total_credit.toLocaleString()}</div>
                          <div style={{color: '#e11d48', fontSize: '0.95rem', fontWeight: 700}}>- ₹{res.total_debit.toLocaleString()}</div>
                        </td>
                        <td style={{ textAlign: 'right' }}>
                          <motion.a 
                            href={`${API_BASE}${res.download_url}`} 
                            className="btn" 
                            style={{padding: '0.6rem', background: '#3b82f6', color: 'white'}}
                            whileHover={{ scale: 1.1 }}
                            whileTap={{ scale: 0.9 }}
                          >
                            <Download size={20} />
                          </motion.a>
                        </td>
                      </motion.tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </main>

      <footer style={{ textAlign: 'center', color: '#94a3b8', fontSize: '0.85rem', marginTop: '4rem', fontWeight: 600, letterSpacing: '0.05em'}}>
        POWERED BY DYNAMIC COORDINATE-MAPPING ENGINE v2.0
      </footer>
    </div>
  );
};

export default App;
