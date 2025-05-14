import React, { useState } from 'react';
import axios from 'axios';
import './App.css';

function App() {
  const [repoUrl, setRepoUrl] = useState('');
  const [token, setToken] = useState('');
  const [query, setQuery] = useState('');
  const [response, setResponse] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResponse(null);

    // Combine inputs into a single user_input string
    const userInput = `${query}\nRepo URL: ${repoUrl}\nToken: ${token}`;

    try {
      const res = await axios.post('http://localhost:8000/api/orchestrate/', {
        user_input: userInput,
      });
      setResponse(res.data);
    } catch (err) {
      setError(err.response?.data?.message || 'Failed to fetch analysis');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="App">
      <h1>Strange Agent Chat</h1>
      <form onSubmit={handleSubmit}>
        <div>
          <label>GitHub Repo URL:</label>
          <input
            type="text"
            value={repoUrl}
            onChange={(e) => setRepoUrl(e.target.value)}
            placeholder="https://github.com/.../..."
            required
          />
        </div>
        <div>
          <label>GitHub Token:</label>
          <input
            type="text"
            value={token}
            onChange={(e) => setToken(e.target.value)}
            placeholder="ghp_YourTokenHere"
            required
          />
        </div>
        <div>
          <label>Query:</label>
          <textarea
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="e.g., Analyze MVC in this repo"
            rows="4"
            required
          />
        </div>
        <button type="submit" disabled={loading}>
          {loading ? 'Analyzing...' : 'Send Query'}
        </button>
      </form>

      {error && (
        <div className="error">
          <h3>Error</h3>
          <p>{error}</p>
        </div>
      )}

      {response && (
        <div className="response">
          <h3>Analysis Results</h3>
          <pre>{JSON.stringify(response, null, 2)}</pre>
        </div>
      )}
    </div>
  );
}

export default App;