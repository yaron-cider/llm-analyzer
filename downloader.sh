#!/bin/bash
apt update
apt install zip -y
# Ensure script has an input parameter for AWS region
if [ "$#" -ne 2 ]; then
  echo "Usage: $0 <csv_file> <aws-region>"
  exit 1
fi

csv_file="$1"
aws_region="$2"

# Check if the required AWS CLI is installed
if ! command -v aws &> /dev/null; then
  echo "AWS CLI could not be found. Please install it to proceed."
  exit 1
fi
results_bucket=$(aws s3 ls | grep bc-scanner-results | sed 's/.* \(bc-scanner-results.*\)/\1/' )

# Parse CSV and download files from S3 if the region matches
while IFS=, read -r customer_name repository url default_branch repo_score package_version is_root count source; do
  # Skip the header row
  if [ "$customer_name" == "customer_name" ]; then
    continue
  fi


  # Check if the source contains the AWS region input
  if [[ "$source" == *"$aws_region"* ]]; then     
     url_part=$(echo $url | sed 's|https://[^/]*/||')
     #echo $url_part
     s3_url="s3://${results_bucket}/checkov/${customer_name}/${url_part}/${default_branch}/all.zip"
     echo "Downloading file for customer: $customer_name from URL: $s3_url"
     #echo $s3_url

    # Use aws s3 cp to download the file from the S3 URL
    aws s3 cp "$s3_url" ./downloaded_repos/$repository/all.zip
    unzip -o ./downloaded_repos/$repository/all.zip -d ./downloaded_repos/$repository
  fi
done < "$csv_file"
