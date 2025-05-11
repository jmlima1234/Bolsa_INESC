#!/bin/bash

# Navigate into backend and run Django server
cd server
python3 manage.py runserver &
BACKEND_PID=$!

# Start frontend
cd ../frontend/frontend
npm install
npm start
FRONTEND_PID=$!

# Wait for backend and frontend to finish
wait $BACKEND_PID
wait $FRONTEND_PID