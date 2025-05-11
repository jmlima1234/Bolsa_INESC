import React, { useState } from 'react';
import axios from 'axios';
import './App.css';

function App() {
  const [repoUrl, setRepoUrl] = useState('');
  const [token, setToken] = useState('');
  const [pattern, setPattern] = useState('');
  const [message, setMessage] = useState('');
  const [results, setResults] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setMessage('');
    setResults(null);

    try {
      const response = await axios.post('http://localhost:8000/api/review/', {
        repo_url: repoUrl,
        token: token,
        architecture: pattern,
      });
      
      setMessage('Success: Analysis complete!');
      setResults(response.data);
    } catch (error) {
      if (error.response) {
        setMessage(`Error: ${error.response.data.message}`);
      } else {
        setMessage('Error: Could not reach backend.');
      }
    }
  };

  return (
    <div className="App">
      <h1>GitHub Repository Pattern Analyzer</h1>
      <form onSubmit={handleSubmit}>
        <div>
          <input
            type="text"
            placeholder="Repository URL"
            value={repoUrl}
            onChange={(e) => setRepoUrl(e.target.value)}
            required
          />
        </div>
        <div>
          <input
            type="text"
            placeholder="GitHub Token (optional)"
            value={token}
            onChange={(e) => setToken(e.target.value)}
          />
        </div>
        <div>
          <input
            type="text"
            placeholder="Architecture Pattern (e.g., MVC)"
            value={pattern}
            onChange={(e) => setPattern(e.target.value)}
            required
          />
        </div>
        <button type="submit">Analyze</button>
      </form>

      {message && <p>{message}</p>}

      {results && (
        <div>
          <h2>Analysis Results</h2>
          <p><strong>Pattern: </strong>{results.pattern}</p>
          <p><strong>Percentage of Pattern Implemented: </strong>{results.percentage}%</p>
          <h3>Explanation:</h3>
          <p>{results.explanation}</p>

          <h3>Improvements:</h3>
          <ul>
            {results.improvements && results.improvements.map((improvement, index) => (
              <li key={index}>
                <strong>{Object.keys(improvement)[0]}: </strong>
                {Object.values(improvement)[0]}
              </li>
            ))}
          </ul>

          <h3>Strengths:</h3>
          <ul>
            {results.strengths && results.strengths.map((strength, index) => (
              <li key={index}>
                <strong>{Object.keys(strength)[0]}: </strong>
                {Object.values(strength)[0]}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

export default App;