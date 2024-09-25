import json
import logging
import os
import subprocess
from git import Repo
from colorama import Fore, Style
import requests
import urllib3
import argparse

CLONE_DIR = "./cloned_repos"
GITHUB_URL = "https://github.com"
DEBUG_MODE = False
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def run_semgrep_and_get_results(path, config=None):
    try:
        result = subprocess.run(['semgrep', '--json', '--config', config, path],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        output = result.stdout.decode()
        return json.loads(output)
    except subprocess.CalledProcessError as e:
        logging.error(f"semgrep failed with exit code {e.returncode}")
        logging.error(f"stderr: {e.stderr.decode()}")
        logging.error(f"stdinfo: {e.stdout.decode()}")

        return
    except Exception as ex:
        logging.error(f"semgrep error: {ex}")
        return

def clone_repo(action_name):
    destination = os.path.expanduser(CLONE_DIR)
    
    if not os.path.exists(destination):
        os.makedirs(destination)

    destination = os.path.join(destination, action_name)
    if not os.path.exists(destination):
        logging.info(f"Cloning action {action_name}")
        clone_url = action_name if GITHUB_URL in action_name else f"{GITHUB_URL}/{action_name}"
        try:
            Repo.clone_from(clone_url, destination, depth=1)
        except Exception as ex:
            logging.error("Repo clone failed " + action_name)
            logging.exception(ex)
            return None
    return destination

def analyze_repo(action_name):  
    repo_path = clone_repo(action_name)
    if repo_path is None:
        return None

    return run_semgrep_and_get_results(repo_path, config="./semgrep-rules/rules.yaml")

def analyze_directory(directory):
    return run_semgrep_and_get_results(directory, config="./semgrep-rules/rules.yaml")     

def print_results(results):
    if not results: 
        return
    unique_rules = set()
    uniqe_buckets = set()
    for rule in results.get('results', []):
        rule_id = rule.get('check_id')
        unique_rules.add(rule_id)

        if rule_id == "semgrep-rules.detect-gs-urls":
            bucket_url = rule.get('extra').get('metavars')['$1']['abstract_content'].replace("'", "").replace('"', "")
            if bucket_url in uniqe_buckets:
                continue
            uniqe_buckets.add(bucket_url)
            print(f"{Fore.LIGHTGREEN_EX}Url: {bucket_url}{Style.RESET_ALL}")

        rule_name = rule.get('extra').get('message')
        lines = rule.get('extra').get('lines').strip()
        if rule_name not in unique_rules:
            unique_rules.add(rule_name)
            print(f"{Fore.GREEN}+ {rule_name}{Style.RESET_ALL}")
        if DEBUG_MODE:
            print(f"{Fore.YELLOW}+++ {lines}{Style.RESET_ALL}")


    for url in uniqe_buckets:
        check_url(url)
    
def check_url(url):
    response = requests.get(transform_gs_url_to_http(url),verify=False)
    if response.status_code == 200:
        print(f"{Fore.LIGHTGREEN_EX} s3 bucket is accessible{Style.RESET_ALL}: {url}")
        return True
    else:
        print(f"{Fore.RED}s3 bucket is not accessible{Style.RESET_ALL}: {url}")
        return False

def transform_gs_url_to_http(url):  
    if url.startswith("gs://"):
        url = url.replace("gs://", "https://storage.googleapis.com/")
    return url

def main():
    #print_results(analyze_repo("recordlydata/vertex-ai-mlops-demo"))
    #print_results(analyze_repo("proppy/python-aiplatform"))
    print_results(analyze_repo("wandb/wandb"))
    
def main():
    parser = argparse.ArgumentParser(description='LLM Analyzer')
    parser.add_argument('--repo', help='GitHub repository name')
    parser.add_argument('--dir', help='Directory name')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')

    args = parser.parse_args()
    global DEBUG_MODE
    if args.debug:
        print("Debug mode enabled")
        DEBUG_MODE = True
    if args.repo:
        print_results(analyze_repo(args.repo))  
    elif args.repo:
        print_results(analyze_directory(args.dir))  
    else:
        parser.print_help()

if __name__ == "__main__":
    main()