try:
    import sys
    import argparse
    from ruamel.yaml import YAML

    import shutil
    import os
    import json
    import sys

    from syftbox.lib import Client
    from sdk import extract_datasite, datasites_file_glob

    __name__ = "fedreduce"

    yaml = YAML()
    yaml.preserve_quotes = True  # Preserve quotes around values
    yaml.indent(mapping=2, sequence=4, offset=2)  # Customize indentation if needed

    def load_yaml(yaml_file_path):
        with open(yaml_file_path, "r") as file:
            data = yaml.load(file)
            return data

    def save_yaml(yaml_file_path, data):
        with open(yaml_file_path, "w") as file:
            yaml.dump(data, file)

    def find_first_yaml_file(directory):
        for root, _, files in os.walk(directory):
            for file in files:
                if file.endswith(".yaml"):
                    return os.path.join(root, file)
        return None

    def main():
        parser = argparse.ArgumentParser(description="Process JSON input.")
        parser.add_argument(
            "--input", type=str, required=True, help="JSON input as a string"
        )
        args = parser.parse_args()

        try:
            # Parse the JSON input into a dictionary
            data = json.loads(args.input)
            client = Client.load()
            command = data["command"]

            if command == "join":
                after_datasite = str(data["source"]).split("/datasites/")[-1]
                source_path = client.sync_folder / after_datasite.replace(
                    "/fedreduce/", "/public/fedreduce/"
                )
                yaml_file = find_first_yaml_file(source_path)
                yaml_file_name = os.path.basename(str(yaml_file))
                datasite = extract_datasite(data["source"])
                folder = (
                    client.sync_folder
                    / client.email
                    / "public"
                    / __name__
                    / "join"
                    / datasite
                )
                if data["state"] == "join":
                    os.makedirs(folder, exist_ok=True)
                    join_file = folder / f"{yaml_file_name}.join"
                    join_file.touch(exist_ok=True)
                    print(json.dumps({"result": "success"}))
                elif data["state"] == "leave":
                    if os.path.exists(folder):
                        shutil.rmtree(folder)
                    print(json.dumps({"result": "success"}))

                sys.exit(0)

            elif command == "list_projects":
                response = []
                projects = datasites_file_glob(
                    client,
                    pattern=f"**/{client.email}/public/{__name__}/**/*.yaml.join",
                )

                for datasite, join_path in projects:
                    project = {}
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

                    project["sourceUrl"] = (
                        f"/datasites/{author}/fedreduce/invite/{api_name}",
                    )
                    response.append(project)
                print(json.dumps(response))
                sys.exit(0)
            elif command == "start":
                path = data["source"]
                datasite = extract_datasite(path)
                print(
                    path,
                    datasite,
                    "/fedreduce/invite/" in path,
                    datasite != client.email,
                    client.email,
                )
                if "/fedreduce/invite/" in path:
                    if datasite != client.email:
                        print(json.dumps({"error": "Not your project, not authorized"}))
                        sys.exit(1)
                    project_name = path.split("/fedreduce/invite/")[-1]

                    # get everyone who has asked to join
                    datasites_joining = datasites_file_glob(
                        client,
                        pattern=f"**/public/{__name__}/join/{client.email}/{project_name}.yaml.join",
                    )

                    join_match = f"/join/{client.email}/{project_name}.yaml.join"
                    joining_datasites = []
                    for datasite, join_path in datasites_joining:
                        if join_match in str(join_path):
                            joining_datasites.append(datasite)

                    redreduce_folder = (
                        client.sync_folder / client.email / "public" / __name__
                    )

                    invite_folder = redreduce_folder / "invite" / project_name
                    running_folder = redreduce_folder / "running"
                    yaml_file = find_first_yaml_file(invite_folder)
                    project = load_yaml(yaml_file)
                    datasites = project.get("workflow", {}).get("datasites", [])
                    if "workflow" not in project:
                        project["workflow"] = {}

                    project["workflow"]["datasites"] = sorted(
                        list(set(datasites + joining_datasites))
                    )
                    save_yaml(yaml_file, project)

                    os.makedirs(running_folder, exist_ok=True)

                    if not os.path.exists(invite_folder) and os.path.exists(
                        running_folder / project_name
                    ):
                        # already running
                        print(json.dumps({"result": "success"}))
                        sys.exit(0)

                    if not os.path.exists(invite_folder):
                        print(json.dumps({"error": "Not a valid project"}))
                        sys.exit(1)

                    if os.path.exists(running_folder / project_name):
                        shutil.rmtree(running_folder / project_name)

                    shutil.move(invite_folder, running_folder)
                    print(json.dumps({"result": "success"}))
                    sys.exit(0)
                else:
                    print(json.dumps({"error": f"not a valid path. {path}"}))
                    sys.exit(1)

        except Exception as e:
            print("error", e)
            sys.exit(1)
        sys.exit(0)

    main()
except Exception as e:
    print("error", e)
    sys.exit(7)
