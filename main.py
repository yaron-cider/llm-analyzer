import json
import logging
import os
import subprocess
from git import Repo
from colorama import Fore, Style
import urllib3
import argparse
import requests
import random

CLONE_DIR = "./cloned_repos"
GITHUB_URL = "https://github.com"
DEBUG_MODE = False
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
NUMBER_OF_FILES_TO_PROCESS = 1

LOCATION = "us-central1"
MODEL = "gemini-2.0-flash-exp"
PROJECT_ID = "asi-ai"
VERTEX_AI_TOKEN = None

def create_AI_token():
    global VERTEX_AI_TOKEN
    print("Creating AI token")
    VERTEX_AI_TOKEN = subprocess.check_output(["gcloud", "auth", "print-access-token"]).decode().strip()
    if not VERTEX_AI_TOKEN:
        raise Exception("AI Helper: Unable to get Vertex AI token")
        

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
            colors = [Fore.LIGHTBLUE_EX, Fore.GREEN, Fore.YELLOW, Fore.BLUE, Fore.MAGENTA, Fore.CYAN, Fore.WHITE]
            color = random.choice(list(colors))
            print(f"{color}+ {rule_name}{Style.RESET_ALL}")
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

def load_file_contents(file_path):
    """
    Read the contents of a file based on its extension.
    Supports Python, JSON, YAML, and plain text files.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as file:           
            return file.read()
            #return f"# File: {os.path.basename(file_path)}\n{file.read()}"
    except Exception as e:
        return f"# Error reading {file_path}: {str(e)}"

def collect_directory_contents(directory_path, allowed_extensions=None):
    """
    Collect contents of files in the specified directory.
    
    :param directory_path: Path to the directory to scan
    :param allowed_extensions: List of allowed file extensions (optional)
    :return: List of file contents
    """
    if allowed_extensions is None:
        allowed_extensions = ['.py', '.json', '.yaml', '.yml', '.txt']
    
    file_contents_arr = []
    
    for root, _, files in os.walk(directory_path):
        for file in files:
            if any(file.endswith(ext) for ext in allowed_extensions):
                full_path = os.path.join(root, file)
                file_contents_arr.append(load_file_contents(full_path))
                if len(file_contents_arr) >= NUMBER_OF_FILES_TO_PROCESS:
                    return file_contents_arr
    
    return file_contents_arr


INSTURCTIONS = '''
                Extract all llm prompts from the code only if you are sure is a prompt. 
                classify prompt system or user input, 
                format answer as pure json object list of prompts with their classification
               '''
                #like follows: {\"prompts\": [{\"prompt\": \"prompt text\", \"classification\": \"system\"}]}"
                #'''


def ollama_chat(path):
    from ollama import chat
    from ollama import ChatResponse
   
    app_code = collect_directory_contents(path)

    print("Estimated number of tokens in context window for the model: ", len(str(app_code)) / 4)

    from ollama import Client
    client = Client(
        host='http://127.0.0.1:11434',
        headers={'x-some-header': 'some-value'}
    )
    # Send to Ollama CodeLlama model
    response = client.chat(model='codellama:13b', messages=[
        {
            'role': 'user',
            #'content': f"Here's the code:\n{app_code}\n\n{INSTURCTIONS}"
            'content': f"{INSTURCTIONS}\n {app_code}"
        }],
       
        format='json'
        )
    '''
    format=json.dumps({ 
        'type': 'object', 
        'properties': {
                        'prompt': { 'type': 'string' }, 
                        'classification': { 'type': 'string' } 
        },
        'required': [
                        'prompt', 
                        'classification'
        ] 
    })
    '''
    

    #print(response['message']['content'])
    # or access fields directly from the response object
    #print(response.message.content)
    prompts = json.loads(response.message.content)
    for prompt in prompts["prompts"]:
        print(prompt)

def get__veheaders():
  
    return headers

def vertex_gemini_chat(path):
      # documentation: https://cloud.google.com/vertex-ai/docs/predictions/generate-content
    app_code = collect_directory_contents(path)

    create_AI_token()
  

    body = {
        "contents" : [
            {
                "role": "user",
                  "parts": [
                    {
                        "text": INSTURCTIONS
                    },
                    {
                        "text": f"Here's the code:\n{app_code}"
                    }
                ]
            }
        ],
        "generationConfig": {
        "candidateCount": 1,
        },
       "safetySettings": [
      {
        "category": "HARM_CATEGORY_UNSPECIFIED",
        "threshold": "BLOCK_NONE"
      },
      {
        "category": "HARM_CATEGORY_HATE_SPEECH",
        "threshold": "BLOCK_NONE"
      },
       {
        "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
        "threshold": "BLOCK_NONE"
      },
       {
        "category": "HARM_CATEGORY_HARASSMENT",
        "threshold": "BLOCK_NONE"
      },
       {
        "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
        "threshold": "BLOCK_NONE"
      }]
          
    }

    headers = {
        'Content-Type' : 'application/json',
        'Authorization' : f'Bearer {VERTEX_AI_TOKEN}'        
    }
    url = f"https://{LOCATION}-aiplatform.googleapis.com/v1/projects/{PROJECT_ID}/locations/{LOCATION}/publishers/google/models/{MODEL}:generateContent"

    response = requests.post(url, verify=False, headers=headers, data=json.dumps(body))
    if response.status_code == 200:
        prompts = json.loads(response.text)["candidates"][0]['content']["parts"][0]["text"]
        print(prompts)
        #for prompt in prompts["prompts"]:
        #    print(prompt)

    else:
        raise(f"AI Helper: generate_text failed with status code {response.status_code}")

   
def main():
    parser = argparse.ArgumentParser(description='PromptProbe')
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
    elif args.dir:
        print_results(analyze_directory(args.dir))  
    else:
        parser.print_help()

def main1():
    #print_results(analyze_repo("recordlydata/vertex-ai-mlops-demo"))
    #print_results(analyze_repo("proppy/python-aiplatform"))
    #vertex_gemini_chat("/Users/yavital/dev/promptprobe/cloned_repos/Kaludii/ChatGPT-Turbo-SMS")
    #ollama_chat("/Users/yavital/dev/promptprobe/cloned_repos/Kaludii/ChatGPT-Turbo-SMS")

    print_results(analyze_repo("PostHog/max-ai"))


if __name__ == "__main__":
    main1()

def process_input(self, user_input: str) -> str:
    # Sanitize user input
    sanitized_input = self._sanitize_input(user_input)  # Implement sanitization function

    # Structure the prompt with dedicated sections
    prompt_payload = {
        "system_prompt": self.system_prompt,
        "user_message": sanitized_input
    }

    # Serialize the data to pass to the model
    prompt = json.dumps(prompt_payload)

    # Generate response
    response = self._generate_response(prompt) # the model should then be configured to parse the structure

    return response


