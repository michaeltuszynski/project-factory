import boto3
from botocore.exceptions import ClientError
import json
import random
import string
import botocore

def get_aws_session(profile_name, region):
    return boto3.Session(profile_name=profile_name, region_name=region)

def generate_random_string(length):
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

def create_s3_bucket(bucket_name, session, project_name, jira_ticket, environment):
    s3_client = session.client('s3')
    region = session.region_name

    # Add a 5-character random string to the bucket name
    random_suffix = generate_random_string(5)
    bucket_name = f"{bucket_name}-{random_suffix}"

    try:
        if region == 'us-east-1':
            s3_client.create_bucket(Bucket=bucket_name)
        else:
            s3_client.create_bucket(
                Bucket=bucket_name,
                CreateBucketConfiguration={'LocationConstraint': region}
            )

        # Enable versioning
        s3_client.put_bucket_versioning(
            Bucket=bucket_name,
            VersioningConfiguration={'Status': 'Enabled'}
        )

        # Add tags
        s3_client.put_bucket_tagging(
            Bucket=bucket_name,
            Tagging={
                'TagSet': [
                    {'Key': 'Project', 'Value': project_name},
                    {'Key': 'JiraTicket', 'Value': jira_ticket},
                    {'Key': 'Environment', 'Value': environment},
                ]
            }
        )

        # Set bucket policy for force_destroy and TLS enforcement
        policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "EnforceTLSRequests",
                    "Effect": "Deny",
                    "Principal": "*",
                    "Action": "s3:*",
                    "Resource": [
                        f"arn:aws:s3:::{bucket_name}/*",
                        f"arn:aws:s3:::{bucket_name}"
                    ],
                    "Condition": {
                        "Bool": {
                            "aws:SecureTransport": "false"
                        }
                    }
                }
            ]
        }
        s3_client.put_bucket_policy(Bucket=bucket_name, Policy=json.dumps(policy))

        print(f"S3 bucket '{bucket_name}' created successfully in region {region} for environment {environment}.")
    except ClientError as e:
        print(f"Error creating S3 bucket: {e}")
        return False
    return bucket_name

def create_dynamodb_table(table_name, session):
    dynamodb = session.resource('dynamodb')
    region = session.region_name

    try:
        table = dynamodb.create_table(
            TableName=table_name,
            KeySchema=[
                {'AttributeName': 'LockID', 'KeyType': 'HASH'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'LockID', 'AttributeType': 'S'}
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        table.wait_until_exists()
        print(f"DynamoDB table '{table_name}' created successfully in region {region}.")
    except ClientError as e:
        print(f"Error creating DynamoDB table: {e}")
        return False
    return True

def setup_terraform_backend(project_name, region, aws_sso_profile, jira_ticket, environment):
    session = get_aws_session(aws_sso_profile, region)
    bucket_name = f"{project_name}-{environment}-terraform-state"
    table_name = f"{project_name}-{environment}-terraform-locks"

    bucket_name = create_s3_bucket(bucket_name, session, project_name, jira_ticket, environment)
    if bucket_name and create_dynamodb_table(table_name, session):
        return bucket_name, table_name
    return None, None

def list_matching_s3_buckets(s3_client, project_name, environment):
    buckets = s3_client.list_buckets()['Buckets']
    prefix = f"{project_name}-{environment}-terraform-state-"
    return [bucket['Name'] for bucket in buckets if bucket['Name'].startswith(prefix)]

def destroy_terraform_backend(project_name, region, aws_sso_profile, environment):
    session = get_aws_session(aws_sso_profile, region)
    s3_client = session.client('s3')
    dynamodb_client = session.client('dynamodb')

    table_name = f"{project_name}-{environment}-terraform-locks"

    # Find and delete matching S3 buckets
    matching_buckets = list_matching_s3_buckets(s3_client, project_name, environment)

    for bucket_name in matching_buckets:
        try:
            # First, delete all objects in the bucket
            paginator = s3_client.get_paginator('list_object_versions')
            for page in paginator.paginate(Bucket=bucket_name):
                objects_to_delete = []
                if 'Versions' in page:
                    objects_to_delete.extend(
                        [{'Key': obj['Key'], 'VersionId': obj['VersionId']} for obj in page['Versions']]
                    )
                if 'DeleteMarkers' in page:
                    objects_to_delete.extend(
                        [{'Key': obj['Key'], 'VersionId': obj['VersionId']} for obj in page['DeleteMarkers']]
                    )
                if objects_to_delete:
                    s3_client.delete_objects(Bucket=bucket_name, Delete={'Objects': objects_to_delete})

            # Then, delete the bucket itself
            s3_client.delete_bucket(Bucket=bucket_name)
            print(f"S3 bucket '{bucket_name}' deleted successfully.")
        except botocore.exceptions.ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchBucket':
                print(f"S3 bucket '{bucket_name}' does not exist.")
            else:
                print(f"Error deleting S3 bucket '{bucket_name}': {e}")
                return False

    if not matching_buckets:
        print(f"No matching S3 buckets found for project '{project_name}' and environment '{environment}'.")

    # Delete DynamoDB table
    try:
        dynamodb_client.delete_table(TableName=table_name)
        print(f"DynamoDB table '{table_name}' deletion initiated.")
        waiter = dynamodb_client.get_waiter('table_not_exists')
        waiter.wait(TableName=table_name)
        print(f"DynamoDB table '{table_name}' deleted successfully.")
    except botocore.exceptions.ClientError as e:
        if e.response['Error']['Code'] == 'ResourceNotFoundException':
            print(f"DynamoDB table '{table_name}' does not exist.")
        else:
            print(f"Error deleting DynamoDB table '{table_name}': {e}")
            return False

    return True
