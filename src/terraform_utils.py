import os
from jinja2 import Environment, FileSystemLoader

def create_terraform_files(project_dir, config):
    template_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates')
    jinja_env = Environment(loader=FileSystemLoader(template_dir))

    tf_files = ['main.tf', 'variables.tf', 'outputs.tf', 'provider.tf']

    for file in tf_files:
        template = jinja_env.get_template(f'terraform/{file}.j2')
        rendered_content = template.render(
            project_name=config['project_name'],
            aws_region=config['aws_region'],
            environment=config['environment'],
            s3_bucket=config['s3_bucket'],
            dynamodb_table=config['dynamodb_table']
        )

        with open(os.path.join(project_dir, file), 'w') as f:
            f.write(rendered_content)

    print(f"Created Terraform files: {', '.join(tf_files)}")

def create_tfvars_files(project_dir, config):
    template_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates')
    jinja_env = Environment(loader=FileSystemLoader(template_dir))

    vars_dir = os.path.join(project_dir, 'vars')
    os.makedirs(vars_dir, exist_ok=True)

    template = jinja_env.get_template(f'vars/{config["environment"]}.tfvars.j2')
    rendered_content = template.render(
        project_name=config['project_name'],
        aws_region=config['aws_region'],
        environment=config['environment'],
        jira_ticket=config['jira_ticket'],
        test_email=config['test_email']
    )

    with open(os.path.join(vars_dir, f'{config["environment"]}.tfvars'), 'w') as f:
        f.write(rendered_content)

    print(f"Created .tfvars file for environment: {config['environment']}")

def create_terraform_template(project_name, infrastructure_dir, s3_bucket, dynamodb_table, aws_region, environment, jira_ticket, test_email):
    # Remove the creation of an extra project directory
    # os.makedirs(project_dir, exist_ok=True)

    config = {
        'project_name': project_name,
        'aws_region': aws_region,
        'environment': environment,
        's3_bucket': s3_bucket,
        'dynamodb_table': dynamodb_table,
        'jira_ticket': jira_ticket,
        'test_email': test_email
    }

    create_terraform_files(infrastructure_dir, config)
    create_tfvars_files(infrastructure_dir, config)

    return infrastructure_dir