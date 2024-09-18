# Infrastructure Project Provisioner

This tool automates the process of setting up infrastructure projects with Terraform, AWS, and GitHub. It creates a standardized project structure, sets up Terraform backend resources in AWS, and initializes a GitHub repository with the necessary files and workflows.

## Features

- Automated setup of Terraform backend (S3 bucket and DynamoDB table) in AWS
- Creation of a GitHub repository with initial project structure
- Generation of Terraform configuration files
- Creation of GitHub Actions workflows for deployment and destruction
- Support for multiple environments (e.g., staging, production)
- Secure secret management using 1Password
- Automated cleanup and resource destruction

## Prerequisites

- Python 3.7+
- AWS CLI configured with appropriate permissions
- GitHub account with personal access token
- 1Password CLI installed and configured

## Installation

1. Clone this repository:
   ```
   git clone https://github.com/your-username/infrastructure-project-provisioner.git
   cd infrastructure-project-provisioner
   ```

2. Install the required Python packages:
   ```
   pip install -r requirements.txt
   ```

## Configuration

1. Copy the `config-template.json` to `config.json`:
   ```
   cp config-template.json config.json
   ```

2. Edit `config.json` with your project-specific information:
   ```json
   {
     "project_name": "your-project-name",
     "working_dir": "/path/to/your/working/directory",
     "jira_ticket": "PROJ-1234",
     "aws_sso_profile": "your-aws-sso-profile",
     "aws_region": "us-east-1",
     "onepassword_vault": "your-1password-vault",
     "onepassword_item": "your-1password-item",
     "environment": "staging",
     "test_email": "your-email@example.com"
   }
   ```

## Usage

### Creating a New Infrastructure Project

To create a new infrastructure project:

```
python main.py --config config.json
```

This will:
1. Set up the Terraform backend in AWS (S3 bucket and DynamoDB table)
2. Create a new GitHub repository
3. Generate Terraform configuration files
4. Create GitHub Actions workflows
5. Commit and push the initial project structure to the GitHub repository

### Destroying Resources

To destroy the created resources:

```
python main.py --config config.json --destroy
```

This will:
1. Destroy the AWS resources (S3 bucket and DynamoDB table)
2. Delete the GitHub repository
3. Remove the local project folder

## Project Structure

The generated project will have the following structure (both locally and in the GitHub repository):

```
working_directory/
```

## Key Components

### AWS Utils (`src/aws_utils.py`)
- Sets up and destroys Terraform backend resources in AWS
- Handles S3 bucket and DynamoDB table creation and deletion

### GitHub Utils (`src/github_utils.py`)
- Creates and deletes GitHub repositories
- Handles file commits and pushes
- Generates GitHub Actions workflows

### Terraform Utils (`src/terraform_utils.py`)
- Generates Terraform configuration files
- Creates environment-specific `.tfvars` files

### Secrets Manager (`src/secrets_manager.py`)
- Retrieves secrets from 1Password

### Main Script (`main.py`)
- Orchestrates the entire process of setting up or destroying the infrastructure project

## GitHub Actions Workflows

Two GitHub Actions workflows are created:

1. `deploy.yml`: Used to plan and apply Terraform changes
2. `destroy.yml`: Used to destroy the Terraform-managed infrastructure

Both workflows use AWS SSO for authentication and can be triggered manually through the GitHub Actions UI.

## Terraform Configuration

The Terraform configuration includes:

- Backend configuration for S3 and DynamoDB
- AWS provider setup
