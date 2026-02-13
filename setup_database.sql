-- Run this in PostgreSQL (psql) or pgAdmin to create the database and users table

-- Create database (if it doesn't exist)
CREATE DATABASE ssdass;

-- Connect to the database
\c ssdass

-- Create users table
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(120) UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Verify table was created
SELECT * FROM users;
