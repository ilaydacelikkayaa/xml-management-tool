# Azure DevOps XML Management Tool

A web-based management tool for Azure DevOps Server (on-premises), developed using FastAPI and React.

## Features

- Work Item Type XML management
- Field listing, addition, updating and UI visibility management
- GlobalList management
- Multi-project preview operations
- XML validation and backup
- Preview and confirmation before applying changes

## Tech Stack

- Backend: Python, FastAPI
- Frontend: React, Vite
- Integration: Azure DevOps Server, REST API, WinRM, witadmin

## Requirements

- Python 3.10+
- Node.js and npm
- Access to Azure DevOps Server
- Windows Server with witadmin and WinRM configured

## Installation

Clone the repository and open the project directory.

### Backend

Install dependencies:

    pip install -r requirements.txt

Create a .env file based on .env.example and configure your own server credentials.

Start the backend:

    uvicorn api:app --reload --port 8003

### Frontend

    cd frontend
    npm install
    npm run dev

Open the local URL displayed by Vite.

## Configuration

Environment variables are documented in `.env.example`.

Do not commit passwords, personal access tokens, or production credentials.

## Notes

- XML import operations should be tested in a dedicated test collection.
- Preview and backup operations are recommended before applying changes.
- The target Azure DevOps environment must support the required XML process management operations.
