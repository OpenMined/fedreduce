import json
import shutil

from typing import Dict, Any
import os
import yaml
import os
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
from run import run_steps_for_email, check_done


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
    public_running_fedreduce_folder = public_fedreduce_folder / "running"

    os.makedirs(public_fedreduce_folder, exist_ok=True)
    os.makedirs(public_invite_fedreduce_folder, exist_ok=True)
    os.makedirs(public_join_fedreduce_folder, exist_ok=True)
    os.makedirs(public_running_fedreduce_folder, exist_ok=True)

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


def extract_last_two_parts(yaml_path: str) -> str:
    """Extract the last two parts of the YAML path."""
    # Split the path into parts
    path_parts = yaml_path.split(os.sep)

    # Join the last two parts to get the desired output
    last_two_parts = os.path.join(path_parts[-2], path_parts[-1])
    return f"/{last_two_parts}"


def extract_last_part(yaml_path: str) -> str:
    """Extract the last parts of the YAML path."""
    # Split the path into parts
    path_parts = yaml_path.split(os.sep)

    # Join the last two parts to get the desired output
    last_part = os.path.join(path_parts[-1])
    return f"/{last_part}"


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
    elif "complete" in str(yaml_path):
        state = "complete"
    else:
        print("Unknown state", yaml_path)

    # Extract datasites from the workflow section
    datasites = yaml_data.get("workflow", {}).get("datasites", [])
    if isinstance(datasites, dict) and "*datasites" in datasites:
        datasites = datasites.get("*datasites", [])

    datasites = list(datasites)

    last_part = extract_last_part(str(yaml_path))

    join_projects = datasites_file_glob(
        client, pattern=f"**/public/{__name__}/**/{last_part}.join"
    )

    print("yaml_path", yaml_path)

    print("join_projects", join_projects)

    for datasite, join_path in join_projects:
        # Extract the datasite email from the join path
        datasite_email = extract_datasite(join_path)

        datasites.append(datasite_email)

    datasites = sorted(list(set(datasites)))
    print("datasites", datasites)

    # Construct base URLs using author and project
    url = public_url(os.path.dirname(yaml_path))
    base_url = "/datasites" + url.split("/datasites")[-1]

    # Generate a nested dictionary under `code` for each file in the YAML's `code` list
    code_files = yaml_data.get("code", [])
    code_data = {file: f"{base_url}/{file}" for file in code_files}

    # Construct the project data with nested `code` dictionary and joined datasites
    project_data = {
        "state": state,
        "name": yaml_data["project"],
        "file_timestamp": timestamp.st_mtime,
        "description": yaml_data["description"],
        "language": yaml_data["language"],
        "author": yaml_data["author"],
        "sourceUrl": base_url,
        "sharedInputs": yaml_data.get("shared_inputs", {}).get("data", ""),
        "datasites": datasites,
        "resultUrl": f"{base_url}/results",
        "code": code_data,  # Nested dictionary for code entries
    }

    return project_data


def generate_activity_json(projects):
    """Generate activity.json from YAML project files."""
    # Initialize project categories
    activity_data = {"invite": [], "running": [], "complete": []}

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
            elif project_data["state"] == "complete":
                activity_data["complete"].append(project_data)

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


def run_projects():
    my_join_projects = datasites_file_glob(
        client, pattern=f"**/{client.email}/public/{__name__}/**/*.yaml.join"
    )

    join_projects = []
    running_projects = []
    complete_projects = []
    for datasite, join_path in my_join_projects:
        print("join_path", join_path)
        project = {}
        project["yaml_join_path"] = join_path
        if "/join/" in str(join_path):
            state = "join"
        elif "/running/" in str(join_path):
            state = "running"
        elif "/complete/" in str(join_path):
            state = "complete"
        else:
            state = "unknown"
        project["state"] = state
        last = str(join_path).split("public/fedreduce/")[-1]
        parts = last.split("/")
        author = None
        for part in parts:
            if "@" in part:
                author = part
        project["author"] = author
        api_name = join_path.name.split(".yaml")[0]
        api_file_name = join_path.name.split(".join")[0]
        project["api_name"] = api_name
        project["api_file_name"] = api_file_name
        if state == "join":
            project_path = (
                client.sync_folder / author / "public" / __name__ / "running" / api_name
            )
        elif state == "running":
            project_path = (
                client.sync_folder / client.email / __name__ / "running" / api_name
            )
        else:
            project_path = (
                client.sync_folder / client.email / __name__ / "complete" / api_name
            )

        project["project_path"] = project_path

        if state == "join":
            join_projects.append(project)
        elif state == "running":
            running_projects.append(project)
        else:
            complete_projects.append(project)

    print("join_projects", join_projects)
    print("running_projects", running_projects)
    print("complete_projects", complete_projects)

    for project in join_projects:
        if os.path.exists(project["project_path"]):
            # move to running
            running_path = Path(
                str(project["yaml_join_path"]).replace("/join/", "/running/")
            )
            os.makedirs(running_path.parent, exist_ok=True)
            shutil.copy(project["yaml_join_path"], running_path.parent)
            old_join_path = Path(project["yaml_join_path"])
            os.unlink(old_join_path)
            os.rmdir(old_join_path.parent)

            project_path = Path(project["project_path"])
            # copy to local datasite
            copy_destination = Path(
                str(project_path)
                .replace(project["author"], client.email)
                .replace("/public/", "/")
            )

            os.makedirs(copy_destination, exist_ok=True)

            if os.path.exists(copy_destination):
                shutil.rmtree(copy_destination)
            shutil.copytree(
                project["project_path"], copy_destination, dirs_exist_ok=True
            )

            project["project_path"] = copy_destination
            project["yaml_join_path"] = running_path
            running_projects.append(project)

    for project in running_projects:
        project_path = Path(project["project_path"])
        public_running = Path(project["yaml_join_path"])
        log_path = str(public_running).replace(".join", ".log")
        pipeline = load_yaml(project_path / project["api_file_name"])
        try:
            run_steps_for_email(
                client,
                pipeline,
                log_file=log_path,
                timeout=120,
            )
        except Exception as e:
            print(f"Error running project {project_path}: {str(e)}")
            continue

        complete, is_author = check_done(
            client,
            pipeline,
            project,
            log_file=log_path,
            timeout=120,
        )
        if complete:
            complete_projects.append(project)

        print("complete", complete)

        if complete:
            if is_author:
                # move public src author only
                redreduce_folder = (
                    client.sync_folder / client.email / "public" / __name__
                )
                running_folder = redreduce_folder / "running" / project["api_name"]
                complete_folder = redreduce_folder / "complete" / project["api_name"]

                print("running_folder", running_folder)
                print("complete_folder", complete_folder)

                os.makedirs(complete_folder, exist_ok=True)

                if os.path.exists(running_folder):
                    # already complete"
                    print("already complete")
                    if os.path.exists(complete_folder):
                        shutil.rmtree(complete_folder)

                    shutil.move(running_folder, complete_folder.parent)

                if os.path.exists(running_folder):
                    shutil.rmtree(running_folder)

                print("public source is now in compelted state")

            # move the public join file and logs to complete
            complete_path = Path(
                str(project["yaml_join_path"]).replace("/running/", "/complete/")
            )
            print("complete_path", complete_path)

            os.makedirs(complete_path.parent, exist_ok=True)

            shutil.copy(project["yaml_join_path"], complete_path.parent)
            old_join_path = Path(project["yaml_join_path"])

            log_file = str(project["yaml_join_path"]).replace(".join", ".log")
            shutil.copy(log_file, complete_path.parent)

            if os.path.exists(old_join_path):
                os.unlink(old_join_path)

            if os.path.exists(log_file):
                os.unlink(log_file)

            try:
                if os.path.exists(old_join_path.parent):
                    os.rmdir(old_join_path.parent)
            except Exception as e:
                print("unable to remove", old_join_path.parent, e)

            # finished moving the join file and logs to complete

            # move private source to complete
            project_path = Path(project["project_path"])
            # copy to local datasite
            copy_destination = Path(
                str(project_path).replace("/running/", "/complete/")
            )

            os.makedirs(copy_destination, exist_ok=True)

            if os.path.exists(copy_destination):
                shutil.rmtree(copy_destination)

            shutil.copytree(
                project["project_path"], copy_destination, dirs_exist_ok=True
            )

            if os.path.exists(project["project_path"]):
                shutil.rmtree(project["project_path"])

            project["project_path"] = copy_destination
            project["state"] = "complete"
            complete_projects.append(project)

    print(complete_projects)


create_folders()
generate_home()
run_projects()
# manual = bool(os.environ.get("MANUAL", False))
# if manual:
#     run_projects()
# else:
#     print("skipping run_projects")
