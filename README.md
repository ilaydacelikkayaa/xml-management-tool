# Azure DevOps XML Management Tool

**A centralized web-based platform for managing, analyzing, validating, and version-controlling Azure DevOps Server XML process definitions.**

Built with **Python, FastAPI, React, and REST APIs**, this project simplifies XML-based process customization in on-premises Azure DevOps environments while introducing safer change management, backup workflows, and Git-based version control.

![Python](https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-149ECA?style=flat-square&logo=react&logoColor=white)
![Azure DevOps](https://img.shields.io/badge/Azure_DevOps-0078D7?style=flat-square&logo=azuredevops&logoColor=white)
![GitHub](https://img.shields.io/badge/GitHub-181717?style=flat-square&logo=github&logoColor=white)

---

## Overview

Managing Work Item Type (WIT) definitions in Azure DevOps Server often requires manually exporting, editing, validating, and importing XML files.

As projects grow, XML configurations become increasingly complex. Unused fields accumulate, GlobalLists become harder to maintain, and manual modifications introduce the risk of configuration errors.

**Azure DevOps XML Management Tool** addresses these challenges through a centralized interface that combines XML process management, field usage analysis, controlled modification workflows, and integration with Git-based repositories.

The project was developed as part of a DevOps and Platform Engineering internship at **VakıfBank**.

## Key Features

### 1. Work Item Type XML Management

Manage XML-based Work Item Type definitions through a web interface.

- Retrieve and inspect WIT XML definitions.
- List existing fields and their properties.
- Add new fields to XML definitions.
- Update existing field configurations.
- Remove selected fields.
- Manage field visibility within the Work Item Type layout.
- Validate XML changes before applying them.

### 2. Field Usage Analysis & Garbage Cleanup

Identify potentially obsolete fields and simplify complex XML configurations.

- Analyze field usage across work items.
- Identify unused or empty fields.
- Review field references before removal.
- Select multiple fields for bulk cleanup.
- Validate cleanup operations before execution.
- Apply controlled field removal workflows.

The cleanup functionality supports safer XML maintenance by helping users review field dependencies before making changes.

### 3. GlobalLists Management

Manage reusable GlobalList definitions and their values.

- View and inspect GlobalLists.
- Add, update, and remove list items.
- Perform bulk editing operations.
- Work with XML and Excel-based editing workflows.
- Simplify the maintenance of large shared value lists.

### 4. GitHub Integration

Integrate XML management workflows with GitHub repositories.

- Pull XML definitions from GitHub.
- Push updated XML content to a configured repository.
- Browse XML commit history.
- Compare XML revisions using commit diffs.
- Create and manage XML backups.
- Perform baseline checks before relevant operations.
- Use Git commit history to improve change traceability.

### 5. Azure Repos Integration

Extend XML version-control workflows to Azure DevOps repositories.

- Access repository-based XML history.
- Integrate XML operations with Azure Repos.
- Support automatic XML backup workflows.
- Improve visibility into configuration changes.

### 6. Preview, Validation & Backup

Introduce safeguards around XML modifications.

- Preview changes before applying them.
- Perform validation and pre-apply checks.
- Create backups before relevant modification operations.
- Support controlled import workflows.
- Compare expected and actual XML definitions when verifying changes.
- Surface operation results and errors through the interface.

### 7. Multi-Project XML Management

Support XML modification workflows across multiple Azure DevOps projects.

- Select multiple target projects.
- Prepare project-specific XML changes.
- Generate separate previews.
- Perform per-project validation.
- Review operation results independently for each project.

### 8. React Web Interface

Provide a centralized frontend for XML management.

- Work Item Type field management.
- GlobalLists management.
- Garbage Cleanup workspace.
- GitHub history and diff views.
- Azure Repos history.
- XML operation previews.
- Validation feedback and confirmation dialogs.

---

## Technology Stack

| Layer | Technologies |
|---|---|
| Backend | Python, FastAPI, Pydantic |
| Frontend | React, JavaScript, Vite |
| XML Processing | Python XML libraries |
| DevOps Platform | Azure DevOps Server 2022 |
| Version Control | Git, GitHub, Azure Repos |
| Integration | REST APIs, `witadmin`, WinRM |
| Authentication | Personal Access Tokens, Windows credentials |
| Data Formats | XML, JSON, Excel |
| Development Environment | macOS, Windows Server |

## System Architecture

The application follows a frontend–backend architecture.

```text
                    USER
                      |
                      v
             +------------------+
             |   React Frontend |
             |       Vite       |
             +------------------+
                      |
                      | HTTP / REST API
                      v
             +------------------+
             |  FastAPI Backend |
             +------------------+
                      |
          +-----------+-----------+
          |           |           |
          v           v           v
   +------------+ +---------+ +------------+
   | Azure      | | GitHub  | | Azure      |
   | DevOps     | | REST API| | Repos      |
   | Server     | |         | |            |
   +------------+ +---------+ +------------+
          |
          v
   +--------------------+
   | WIT XML Management |
   | witadmin / WinRM   |
   +--------------------+
          |
          v
   +--------------------+
   | Preview            |
   | Validation         |
   | Backup             |
   | Import / Verify    |
   +--------------------+
```

### Backend Responsibilities

The backend handles XML processing, API integrations, validation, field usage analysis, backup operations, and communication with Azure DevOps Server.

### Frontend Responsibilities

The React frontend provides interactive workflows for XML configuration management, repository history inspection, cleanup operations, and user confirmations.

---

## Project Structure

```text
xml-management-tool/
|
|-- api.py
|-- devops_backend.py
|-- github_service.py
|-- requirements.txt
|-- .env.example
|-- .gitignore
|-- README.md
|
|-- frontend/
|   |-- src/
|   |   |-- components/
|   |   |   |-- AzureReposHistory.jsx
|   |   |   |-- GarbageCleanup.jsx
|   |   |   |-- GitHubHistory.jsx
|   |   |   `-- ...
|   |   `-- ...
|   |-- package.json
|   `-- ...
|
`-- xml-definitions/
    |-- sample.xml
    `-- XMLLabCollection/
        `-- XMLManagementLab/
            `-- Issue.xml
```

### Main Backend Modules

| File | Responsibility |
|---|---|
| `api.py` | FastAPI routes and application operations |
| `devops_backend.py` | Azure DevOps Server integration and XML management logic |
| `github_service.py` | GitHub repository and XML integration |

---

## Installation & Setup

### Prerequisites

- Python 3.10+
- Node.js and npm
- Git
- Access to an Azure DevOps Server environment
- Appropriate Azure DevOps permissions
- A Windows environment with `witadmin` for applicable XML operations
- WinRM connectivity for workflows that require remote Windows execution
- GitHub or Azure Repos credentials for repository integrations

### 1. Clone the Repository

```bash
git clone https://github.com/ilaydacelikkayaa/xml-management-tool.git
cd xml-management-tool
```

### 2. Set Up the Backend

Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

On Windows, activate the environment using:

```powershell
.venv\Scripts\activate
```

Install the required Python dependencies:

```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables

Copy the example configuration:

```bash
cp .env.example .env
```

Configure the relevant Azure DevOps Server connection details, authentication credentials, and allowed import collections.

The provided `.env.example` includes configuration for:

- Azure DevOps Server URL and authentication
- Windows Server credentials
- WinRM connectivity
- Allowed import collections

Additional GitHub integration settings may be required depending on the operations being used, including repository owner, repository name, branch, file path, and authentication token.

**Never commit `.env`, passwords, access tokens, or production credentials to Git.**

### 4. Start the Backend

```bash
uvicorn api:app --reload --port 8003
```

Backend API:

```text
http://localhost:8003
```

Interactive API documentation:

```text
http://localhost:8003/docs
```

### 5. Start the Frontend

Open another terminal:

```bash
cd frontend
npm install
npm run dev
```

Open the local development URL displayed by Vite.

---

## XML Change Management Workflow

The application is designed around a controlled XML modification process.

```text
Select Collection / Project / WIT
                |
                v
        Retrieve XML
                |
                v
       Analyze / Edit
                |
                v
       Generate Preview
                |
                v
       Validate Changes
                |
                v
       Review & Confirm
                |
                v
       Create XML Backup
                |
                v
        Apply Changes
                |
                v
      Verify Final State
```

This workflow helps reduce risks associated with direct manual XML modification.

## Version Control & Traceability

The project integrates repository-based workflows to make XML configuration changes easier to inspect and track.

**GitHub integration** provides XML pull/push operations, revision history, diffs, and backup-related capabilities.

**Azure Repos integration** extends repository history and backup workflows to Azure DevOps environments.

Together, these capabilities support a more traceable approach to XML configuration management.

## Security & Operational Considerations

XML process modifications can affect multiple work items and projects. Appropriate safeguards are essential.

- Use dedicated test collections before modifying production configurations.
- Review previews and validation results before applying changes.
- Maintain backups of XML definitions.
- Limit import operations to explicitly authorized collections.
- Apply least-privilege access to credentials and repository tokens.
- Avoid committing secrets, local backups, and temporary test artifacts.
- Verify imported XML definitions after modification.
- Review field dependencies before bulk removal.

> **Important:** This project interacts with Azure DevOps Server process definitions. Test all modification workflows in a non-production environment before using them against business-critical projects.

---

## Engineering Highlights

This project demonstrates practical experience with:

- Backend API development using Python and FastAPI
- Frontend development with React
- Azure DevOps Server administration and XML process customization
- REST API integration
- GitHub and Azure Repos integration
- Git-based version control and change traceability
- XML validation and structured configuration management
- Backup and recovery-oriented workflows
- Bulk operations and dependency analysis
- Multi-project change management
- Client-server architecture
- Error handling and operational safeguards

## Development Context

Developed during a **DevOps & Platform Engineering internship at VakıfBank**, the project focuses on reducing manual XML management effort and improving the consistency, traceability, and safety of process configuration changes in an on-premises Azure DevOps Server environment.

The application combines process administration, repository integration, and operational tooling within a single web-based workspace.

## Author

**İlayda Çelikkaya**

Computer Engineering | DevOps & Software Development

[GitHub Profile](https://github.com/ilaydacelikkayaa)

---

*Built to simplify Azure DevOps XML administration through centralized management, validation, automation, and version control.*
