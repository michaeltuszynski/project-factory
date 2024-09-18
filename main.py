import argparse
import os
import json
import shutil
from src.aws_utils import setup_terraform_backend, destroy_terraform_backend
from src.github_utils import create_github_repo, commit_and_push, create_github_workflows, delete_github_repo, init_local_repo_and_push
from src.terraform_utils import create_terraform_template, create_tfvars_files
from src.secrets_manager import get_secrets
from github import GithubException

def load_config(config_path):
    with open(config_path, 'r') as f:
        return json.load(f)

def validate_config(config):
    required_keys = [
        'project_name',
        'working_dir',
        'jira_ticket',
        'aws_sso_profile',
        'aws_region',
        'onepassword_vault',
        'onepassword_item',
        'environment',
        'test_email'
    ]
    missing_keys = [key for key in required_keys if key not in config]
    if missing_keys:
        raise ValueError(f"Missing required keys in config.json: {', '.join(missing_keys)}")

def destroy_resources(config, secrets):
    print(f"Destroying resources for project '{config['project_name']}' in environment '{config['environment']}'...")

    # Destroy AWS resources
    aws_success = destroy_terraform_backend(
        config['project_name'],
        config['aws_region'],
        config['aws_sso_profile'],
        config['environment']
    )

    # Delete GitHub repository
    try:
        github_success = delete_github_repo(config['project_name'], secrets['github_token'])
    except GithubException as e:
        print(f"Error deleting GitHub repository: {e}")
        github_success = False
    except Exception as e:
        print(f"Unexpected error occurred while deleting GitHub repository: {e}")
        github_success = False

    # Remove local project folder
    local_project_path = os.path.join(config['working_dir'], config['project_name'])
    try:
        if os.path.exists(local_project_path):
            shutil.rmtree(local_project_path)
            print(f"Local project folder '{local_project_path}' removed successfully.")
            local_success = True
        else:
            print(f"Local project folder '{local_project_path}' does not exist.")
            local_success = True
    except Exception as e:
        print(f"Error removing local project folder: {e}")
        local_success = False

    if aws_success and github_success and local_success:
        print(f"All resources for project '{config['project_name']}' in environment '{config['environment']}' have been destroyed.")
    else:
        print(f"Failed to destroy some or all resources for project '{config['project_name']}' in environment '{config['environment']}'.")
        if not aws_success:
            print("AWS resources destruction failed.")
        if not github_success:
            print("GitHub repository deletion failed.")
        if not local_success:
            print("Local project folder removal failed.")

def create_scripts_folder(infrastructure_dir):
    scripts_dir = os.path.join(infrastructure_dir, 'scripts')
    os.makedirs(scripts_dir, exist_ok=True)

    # Copy validate_vars.sh to the scripts folder
    source_path = os.path.join(os.path.dirname(__file__), 'templates', 'scripts', 'validate_vars.sh')
    dest_path = os.path.join(scripts_dir, 'validate_vars.sh')
    shutil.copy2(source_path, dest_path)

    print(f"Created scripts folder and added validate_vars.sh")
    return scripts_dir

def main():
    parser = argparse.ArgumentParser(description="Infrastructure Project Provisioner")
    parser.add_argument("--config", default="config.json", help="Path to the configuration file")
    parser.add_argument("--destroy", action="store_true", help="Destroy the created resources")
    args = parser.parse_args()

    try:
        config = load_config(args.config)
        validate_config(config)
    except json.JSONDecodeError as e:
        print(f"Error parsing config.json: {e}")
        return
    except ValueError as e:
        print(f"Invalid config.json: {e}")
        return
    except FileNotFoundError:
        print(f"Config file not found: {args.config}")
        return

    try:
        secrets = get_secrets(config)
    except ValueError as e:
        print(f"Error retrieving secrets: {e}")
        return
    except Exception as e:
        print(f"Unexpected error occurred while retrieving secrets: {e}")
        return

    if args.destroy:
        destroy_resources(config, secrets)
        return

    # Setup Terraform backend
    s3_bucket, dynamodb_table = setup_terraform_backend(
        config['project_name'],
        config['aws_region'],
        config['aws_sso_profile'],
        config['jira_ticket'],
        config['environment']
    )

    if not s3_bucket or not dynamodb_table:
        print("Failed to create Terraform backend. Exiting.")
        return

    # Update config with the new S3 bucket name
    config['s3_bucket'] = s3_bucket

    # Create project directory
    project_dir = os.path.join(config['working_dir'], config['project_name'])
    os.makedirs(project_dir, exist_ok=True)

    # Create infrastructure directory
    infrastructure_dir = os.path.join(project_dir, 'infrastructure')
    os.makedirs(infrastructure_dir, exist_ok=True)

    # Create Terraform template
    tf_dir = create_terraform_template(
        config['project_name'],
        infrastructure_dir,
        s3_bucket,
        dynamodb_table,
        config['aws_region'],
        config['environment'],
        config['jira_ticket'],
        config['test_email']
    )

    # Create scripts folder and add validate_vars.sh
    scripts_dir = create_scripts_folder(infrastructure_dir)

    # Create tfvars file
    tfvars_config = {
        'project_name': config['project_name'],
        'aws_region': config['aws_region'],
        'environment': config['environment'],
        'jira_ticket': config['jira_ticket'],
        'test_email': config['test_email']
    }
    create_tfvars_files(tf_dir, tfvars_config)

    # Create GitHub workflows
    deploy_path, destroy_path = create_github_workflows(
        project_dir,
        config['environment'],
        config['project_name'],
        config['aws_region']
    )

    # Setup GitHub repo
    try:
        repo = create_github_repo(config['project_name'], secrets['github_token'], config['environment'])
    except GithubException as e:
        print(f"Error creating GitHub repository: {e}")
        print("Terraform template and workflows are available locally.")
        return
    except Exception as e:
        print(f"Unexpected error occurred while creating GitHub repository: {e}")
        print("Terraform template and workflows are available locally.")
        return

    if repo:
        # Commit and push Terraform template and workflows
        files_to_commit = [
            (os.path.join(tf_dir, 'main.tf'), "infrastructure/main.tf"),
            (os.path.join(tf_dir, 'variables.tf'), "infrastructure/variables.tf"),
            (os.path.join(tf_dir, 'outputs.tf'), "infrastructure/outputs.tf"),
            (os.path.join(tf_dir, 'provider.tf'), "infrastructure/provider.tf"),
            (os.path.join(tf_dir, 'vars', f"{config['environment']}.tfvars"), f"infrastructure/vars/{config['environment']}.tfvars"),
            (os.path.join(scripts_dir, 'validate_vars.sh'), "infrastructure/scripts/validate_vars.sh"),
            (deploy_path, '.github/workflows/deploy.yml'),
            (destroy_path, '.github/workflows/destroy.yml'),
        ]

        commit_errors = []
        for local_path, repo_path in files_to_commit:
            try:
                with open(local_path, 'r') as f:
                    content = f.read()
                commit_and_push(repo, repo_path, f"Add {repo_path} for {config['project_name']}", content)
            except GithubException as e:
                commit_errors.append(f"Error committing {repo_path}: {e}")
            except Exception as e:
                commit_errors.append(f"Unexpected error committing {repo_path}: {e}")

        if commit_errors:
            print("Errors occurred while committing files:")
            for error in commit_errors:
                print(error)
            print("Some files may not have been committed successfully.")
        else:
            # Initialize local repo and push to GitHub
            repo_url = repo.clone_url
            if init_local_repo_and_push(project_dir, repo_url, config['environment']):
                print(f"Local repository initialized and '{config['environment']}' branch pushed to GitHub.")
            else:
                print(f"Failed to initialize local repository or push '{config['environment']}' branch to GitHub.")

            print(f"Infrastructure project '{config['project_name']}' has been provisioned successfully for environment '{config['environment']}'!")
            print(f"GitHub repository: {repo.html_url}")
            print(f"Terraform backend:")
            print(f"  S3 bucket: {s3_bucket}")
            print(f"  DynamoDB table: {dynamodb_table}")
            print(f"  AWS Region: {config['aws_region']}")
            print(f"Local project directory: {project_dir}")
            print("GitHub Actions workflows for deploy and destroy have been added to the repository.")
            print("\nNOTE: This project uses organization secrets for AWS roles:")
            print("- 'AWS_ROLE_TO_ASSUME' for production environment")
            print("- 'SANDBOX_AWS_ROLE_TO_ASSUME' for development environment")
            print("Ensure these secrets are properly set in your GitHub organization settings.")
    else:
        print("Failed to create GitHub repository. Terraform template and workflows are available locally.")

if __name__ == "__main__":
    main()
