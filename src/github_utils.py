import os
from jinja2 import Environment, FileSystemLoader
from github import Github, GithubException
import subprocess

def create_github_repo(project_name, github_token, environment):
    g = Github(github_token)
    user = g.get_user()

    try:
        repo = user.create_repo(project_name, private=True, auto_init=True)
        print(f"GitHub repository '{project_name}' created successfully.")

        # Get the default branch
        default_branch = repo.default_branch

        # Create a new branch for the environment
        sb = repo.get_branch(default_branch)
        repo.create_git_ref(ref=f"refs/heads/{environment}", sha=sb.commit.sha)
        print(f"Created new branch '{environment}'.")

        # Set the new branch as the default
        repo.edit(default_branch=environment)
        print(f"Set '{environment}' as the default branch.")

        # Delete the old default branch
        repo.get_git_ref(f"heads/{default_branch}").delete()
        print(f"Deleted old default branch '{default_branch}'.")

        return repo
    except GithubException as e:
        print(f"Error creating GitHub repository: {e}")
        return None

def commit_and_push(repo, file_path, commit_message, content):
    try:
        repo.create_file(file_path, commit_message, content)
        print(f"File '{file_path}' committed and pushed successfully.")
    except GithubException as e:
        print(f"Error committing and pushing file: {e}")

def create_github_workflows(project_dir, environment, project_name, aws_region):
    workflows_dir = os.path.join(project_dir, '.github', 'workflows')
    os.makedirs(workflows_dir, exist_ok=True)

    template_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates')
    jinja_env = Environment(loader=FileSystemLoader(template_dir))

    workflow_files = ['deploy.yml', 'destroy.yml']

    for file in workflow_files:
        template = jinja_env.get_template(f'github_workflows/{file}.j2')
        rendered_content = template.render(
            environment=environment,
            project_name=project_name,
            aws_region=aws_region
        )

        with open(os.path.join(workflows_dir, file), 'w') as f:
            f.write(rendered_content)

    print(f"Created GitHub workflow files: {', '.join(workflow_files)}")
    return [os.path.join(workflows_dir, file) for file in workflow_files]

def delete_github_repo(repo_name, github_token):
    g = Github(github_token)
    user = g.get_user()

    try:
        repo = user.get_repo(repo_name)
        repo.delete()
        print(f"GitHub repository '{repo_name}' deleted successfully.")
        return True
    except GithubException as e:
        if e.status == 404:
            print(f"GitHub repository '{repo_name}' not found.")
        else:
            print(f"Error deleting GitHub repository '{repo_name}': {e}")
        return False

def init_local_repo_and_push(project_dir, repo_url, environment):
    try:
        # Create .gitignore file from template
        template_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates')
        jinja_env = Environment(loader=FileSystemLoader(template_dir))
        gitignore_template = jinja_env.get_template('.gitignore.j2')
        gitignore_content = gitignore_template.render()

        with open(os.path.join(project_dir, '.gitignore'), 'w') as f:
            f.write(gitignore_content)
        print("Created .gitignore file from template.")

        # Initialize local Git repository
        subprocess.run(['git', 'init'], cwd=project_dir, check=True)
        print("Initialized local Git repository.")

        # Add all files (including .gitignore) to staging
        subprocess.run(['git', 'add', '.'], cwd=project_dir, check=True)
        print("Added all files (including .gitignore) to staging.")

        # Commit changes
        subprocess.run(['git', 'commit', '-m', f"Initial commit for {environment} environment"], cwd=project_dir, check=True)
        print(f"Committed changes for {environment} environment, including .gitignore.")

        # Add remote
        subprocess.run(['git', 'remote', 'add', 'origin', repo_url], cwd=project_dir, check=True)
        print(f"Added remote: {repo_url}")

        # Fetch the remote
        subprocess.run(['git', 'fetch'], cwd=project_dir, check=True)

        # Push to remote, setting upstream branch
        subprocess.run(['git', 'push', '-u', 'origin', f"HEAD:{environment}"], cwd=project_dir, check=True)
        print(f"Pushed to '{environment}' branch in remote repository, including .gitignore.")

        return True
    except subprocess.CalledProcessError as e:
        print(f"Error during Git operations: {e}")
        return False