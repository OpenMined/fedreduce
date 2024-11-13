import json

from typing import Dict, Any
import os
import yaml
import os
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import yaml
from syftbox.lib import Client, SyftPermission

from sdk import Settings, datasites_file_glob, ensure, public_url, extract_datasite

client = Client.load()


__name__ = "fedreduce"
__version__ = "1.0.0"
# __author__ = "madhava@openmined.org"
__author__ = "b@openmined.org"


def create_folders():
    private_fedreduce_folder = client.sync_folder / client.email / __name__
    os.makedirs(private_fedreduce_folder, exist_ok=True)

    public_fedreduce_folder = client.sync_folder / client.email / "public" / __name__
    public_invite_fedreduce_folder = public_fedreduce_folder / "invite"
    public_join_fedreduce_folder = public_fedreduce_folder / "join"

    os.makedirs(public_fedreduce_folder, exist_ok=True)
    os.makedirs(public_invite_fedreduce_folder, exist_ok=True)
    os.makedirs(public_join_fedreduce_folder, exist_ok=True)

    permission = SyftPermission.mine_with_public_read(client.email)
    permission.ensure(public_fedreduce_folder)


# settings
settings = Settings()
last_run = settings.get("last_run", None)
settings.set("last_run", datetime.now().isoformat())


DATASITES = Path(client.sync_folder)
MY_DATASITE = DATASITES / client.email
PUBLIC_PATH = MY_DATASITE / "public"
PUBLISH_PATH = PUBLIC_PATH / __name__
HOME_URL = f"{public_url(PUBLISH_PATH)}/index.html"


def load_yaml(file_path):
    with open(file_path, "r") as file:
        return yaml.safe_load(file)


def parse_yaml_project(datasite, yaml_path: str) -> Dict[str, Any]:
    """Parse a project YAML file and return structured data with nested code entries."""
    with open(yaml_path, "r") as f:
        yaml_data = yaml.safe_load(f)

    timestamp = os.stat(yaml_path)

    if datasite != yaml_data["author"]:
        print("Not the author of the datasite, so skipping", yaml_path)
        return

    # Determine the project state from the file path
    state = "invite"
    if "invite" in str(yaml_path):
        state = "invite"
    elif "running" in str(yaml_path):
        state = "running"
    elif "completed" in str(yaml_path):
        state = "completed"
    else:
        print("Unknown state", yaml_path)

    # Extract datasites from the workflow section
    datasites = yaml_data.get("workflow", {}).get("datasites", [])
    if isinstance(datasites, dict) and "*datasites" in datasites:
        datasites = datasites.get("*datasites", [])

    datasites = list(datasites)

    # Additional logic to check joined datasites
    joined_datasites = []
    join_projects = datasites_file_glob(
        client, pattern=f"**/public/{__name__}/**/*.yaml.join"
    )

    for datasite, join_path in join_projects:
        # Extract the datasite email from the join path
        datasite_email = extract_datasite(join_path)

        datasites.append(datasite_email)

    datasites = sorted(list(set(datasites)))

    # Construct base URLs using author and project
    base_url = f"http://syftbox.openmined.org/datasites/{yaml_data['author']}/public/fedreduce/{yaml_data['project']}"

    # Generate a nested dictionary under `code` for each file in the YAML's `code` list
    code_files = yaml_data.get("code", [])
    code_data = {file: f"{base_url}/{file}" for file in code_files}

    # Construct the project data with nested `code` dictionary and joined datasites
    project_data = {
        "state": state,
        "name": yaml_data["project"].capitalize(),
        "file_timestamp": timestamp.st_mtime,
        "uid": yaml_data["uid"],
        "description": yaml_data["description"],
        "language": yaml_data["language"],
        "author": yaml_data["author"],
        "sourceUrl": base_url,
        "sharedInputs": yaml_data.get("shared_inputs", {}).get("data", ""),
        "datasites": datasites,
        "resultUrl": f"{base_url}/results",
        "code": code_data,  # Nested dictionary for code entries
        "joined_datasites": joined_datasites,  # Include joined datasites
    }

    return project_data


def generate_activity_json(projects):
    """Generate activity.json from YAML project files."""
    # Initialize project categories
    activity_data = {"invite": [], "running": [], "completed": []}

    for datasite, yaml_path in projects:
        try:
            project_data = parse_yaml_project(datasite, yaml_path)
            if project_data is None:
                continue

            # Simple logic for status - could be made more sophisticated
            if project_data["state"] == "invite":
                activity_data["invite"].append(project_data)
            elif project_data["state"] == "running":
                activity_data["running"].append(project_data)
            elif project_data["state"] == "completed":
                activity_data["completed"].append(project_data)

        except Exception as e:
            print(traceback.format_exc())
            print(f"Error processing {yaml_path}: {str(e)}")
            continue
    return activity_data


def generate_home():
    """Main function to generate the home page and activity.json."""
    run_analysis = settings.get("run_analysis", None)
    if (run_analysis is None and client.email != __author__) or run_analysis is False:
        return

    # Find all YAML files
    projects = datasites_file_glob(client, pattern=f"**/public/{__name__}/**/*.yaml")
    activity = generate_activity_json(projects)

    output_path = PUBLISH_PATH / "activity.json"
    with open(output_path, "w") as f:
        json.dump(activity, f, indent=2)
        print(f"Writing json to {output_path}")

    # Generate activity.json
    output_path = "./widget/activity.json"
    with open(output_path, "w") as f:
        json.dump(activity, f, indent=2)

    print(f"Dashboard published to {HOME_URL}")

    # Ensure web files are in place
    ensure(
        ["./widget/index.html", "./widget/index.js", "./widget/syftbox-sdk.js"],
        PUBLISH_PATH,
    )


create_folders()
generate_home()
