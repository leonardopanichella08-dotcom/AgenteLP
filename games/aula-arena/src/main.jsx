import React from 'react';
import { createRoot } from 'react-dom/client';
import App from './App.jsx';
import './index.css';

// Blocca zoom a pinch (iOS) e menu contestuale: il gioco gestisce da solo i tocchi.
['gesturestart', 'gesturechange', 'gestureend'].forEach((ev) =>
  document.addEventListener(ev, (e) => e.preventDefault(), { passive: false }),
);
document.addEventListener('contextmenu', (e) => e.preventDefault());

createRoot(document.getElementById('root')).render(<App />);
