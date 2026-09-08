import { useState } from 'react'
import axios from 'axios'

function App() {
  const [message, setMessage] = useState('')
  const [response, setResponse] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

    const handleSend = async () => {
    if (!message.trim()) return

    setLoading(true)
    setError('')
    setResponse('')

    try {
      // Send natural language query to Coordinator Agent
      const res = await axios.post('http://localhost:8000/query', {
        query: message
      })

      if (res.data.status === 'blocked') {
        setError(res.data.message)
      } else if (res.data.routing) {
        setResponse(JSON.stringify(res.data.routing, null, 2))
      } else {
        setResponse(JSON.stringify(res.data, null, 2))
      }
    } catch (err) {
      setError(`Connection Error: ${err.message}`)
    } finally {
      setLoading(false)
    }
  }


  return (
    <div className="container">
      <h1>📦 IntelliWMS Assistant</h1>
      <p className="subtitle">AI-Powered Warehouse Routing & Operations</p>
      
      <div className="chat-box">
        <input
          type="text"
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSend()}
          placeholder="e.g. Check stock for SKU-4521 or where is aisle 12..."
          disabled={loading}
        />
        <button onClick={handleSend} disabled={loading}>
          {loading ? 'Connecting...' : 'Send'}
        </button>
      </div>

      {response && (
        <div className="card response">
          <strong>Backend Connected:</strong>
          <pre>{response}</pre>
        </div>
      )}

      {error && (
        <div className="card error">
          <strong>Alert:</strong>
          <p>{error}</p>
        </div>
      )}
    </div>
  )
}

export default App
