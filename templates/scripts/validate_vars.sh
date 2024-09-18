#!/bin/bash
set -e

if [ -z "$1" ]; then
  echo "Usage: $0 <path_to_tfvars>"
  exit 1
fi

TFVARS_FILE=$1

# Extract variables that do not have a default value
awk '/variable/ {print $2}' variables.tf | tr -d '"' > /tmp/all_vars.txt
awk '/variable/ {flag=1; next} /}/ {flag=0} flag && /default/ {print prev} {prev=$2}' variables.tf | tr -d '"' > /tmp/default_vars.txt
comm -23 <(sort /tmp/all_vars.txt) <(sort /tmp/default_vars.txt) > /tmp/required_vars.txt

# Print extracted required variables
#echo "Required variables without default values:"
#cat /tmp/required_vars.txt

# Read defined variables from the tfvars file into an array
DEFINED_VARS=()
while IFS= read -r line; do
  DEFINED_VARS+=("$line")
done < <(awk -F '=' '{print $1}' "$TFVARS_FILE" | tr -d ' ')

# Check if all required variables are defined in the tfvars file
REQUIRED_VARS=$(cat /tmp/required_vars.txt)

for var in $REQUIRED_VARS; do
  if ! [[ " ${DEFINED_VARS[@]} " =~ " ${var} " ]]; then
    echo "Error: Required variable '$var' is not defined in $TFVARS_FILE"
    exit 1
  fi
done

echo "All required variables are defined in $TFVARS_FILE"