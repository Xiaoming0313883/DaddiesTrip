import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)

// Fade out and remove the inline splash screen once React has mounted
const splash = document.getElementById('splash')
if (splash) {
  splash.style.opacity = '0'
  setTimeout(() => splash.remove(), 400)
}
