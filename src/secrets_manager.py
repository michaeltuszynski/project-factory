import subprocess
import json

def get_secret(vault, item, field):
    try:
        result = subprocess.run(
            ['op', 'item', 'get', item, '--vault', vault, '--field', field],
            capture_output=True, text=True, check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Error retrieving secret '{field}' from 1Password: {e}")
        return None

def get_secrets(config):
    vault = config['onepassword_vault']
    item = config['onepassword_item']

    required_secrets = [
        'github_token'
    ]

    secrets = {}
    for secret_name in required_secrets:
        secret_value = get_secret(vault, item, secret_name)
        if secret_value is None:
            raise ValueError(f"Failed to retrieve required secret '{secret_name}' from 1Password")
        secrets[secret_name] = secret_value

    return secrets
