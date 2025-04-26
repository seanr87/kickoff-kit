import requests
import sys
import json

def get_project_id(token, owner, project_number):
    """Get the GitHub Project ID (PVT_xxx) using GraphQL API"""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    # GraphQL query for user project
    query = """
    {
      user(login: "%s") {
        projectV2(number: %s) {
          id
          title
        }
      }
    }
    """ % (owner, project_number)
    
    # Make the API request
    response = requests.post(
        "https://api.github.com/graphql",
        headers=headers,
        json={"query": query}
    )
    
    if response.status_code != 200:
        print(f"Error: {response.text}")
        return None
    
    data = response.json()
    if "errors" in data:
        print(f"GraphQL errors: {data['errors']}")
        return None
    
    # Extract project ID
    try:
        project_id = data["data"]["user"]["projectV2"]["id"]
        project_title = data["data"]["user"]["projectV2"]["title"]
        print(f"Found project: {project_title}")
        print(f"Project ID: {project_id}")
        return project_id
    except (KeyError, TypeError):
        print("Could not find project ID in response")
        return None

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python get_project_id.py <github_token> <owner> <project_number>")
        sys.exit(1)
    
    token = sys.argv[1]
    owner = sys.argv[2]
    project_number = sys.argv[3]
    
    project_id = get_project_id(token, owner, project_number)
    if project_id:
        print("\nAdd this to your .pruner.config file:")
        print(f'project_id: "{project_id}"')