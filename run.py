import os
import argparse
import time
from syftbox.lib import Client, SyftPermission
import yaml
from sdk import *


def load_yaml(file_path):
    with open(file_path, "r") as file:
        return yaml.safe_load(file)


def process_template(
    path_template, email, project, step_num, prev_step_num=None, prev_datasite=None
):
    return path_template.format(
        datasite=email,
        project=project,
        step=step_num,
        prev_step=prev_step_num if prev_step_num is not None else step_num - 1,
        prev_datasite=prev_datasite,
    )


def execute_step(
    client, step, email, project, step_num, prev_step_num, prev_datasite, log_file
):
    # Process input_1
    if step["input_1"]["type"] == "StaticPipe":
        input_1 = StaticPipe(step["input_1"]["value"])
    elif step["input_1"]["type"] == "FilePipe":
        input_1_path = process_template(
            step["input_1"]["path"],
            email,
            project,
            step_num,
            prev_step_num,
            prev_datasite,
        )
        print(step, email, "input_1_path", input_1_path)
        input_1_sync_path = client.sync_folder / input_1_path
        print("ABS", input_1_sync_path)
        input_1 = FilePipe(input_1_sync_path)

    # Process input_2
    if step["input_2"]["type"] == "StaticPipe":
        input_2 = StaticPipe(step["input_2"]["value"])
    elif step["input_2"]["type"] == "FilePipe":
        input_2_path = process_template(
            step["input_2"]["path"],
            email,
            project,
            step_num,
            prev_step_num,
            prev_datasite,
        )
        input_2_sync_path = client.sync_folder / input_2_path
        input_2 = FilePipe(input_2_sync_path)
        print(step, email, "input_2_path", input_2.file_path)

    # Perform operation
    operation = step["operation"]
    if operation == "add":
        result = input_1.read() + input_2.read()

    # Process output
    output_path = process_template(
        step["output"]["path"], email, project, step_num, prev_step_num, prev_datasite
    )
    output_sync_path = client.sync_folder / output_path
    folder = os.path.dirname(output_sync_path)
    os.makedirs(folder, exist_ok=True)

    print("output", output_sync_path)
    output = FilePipe(output_sync_path)
    output.write(result)

    # Set permissions
    access_emails = step["output"].get("access", [])
    access_emails = [email] + access_emails

    permission = SyftPermission(
        admin=access_emails, read=access_emails, write=access_emails
    )
    permission.ensure(folder)

    # Log the step execution
    with open(log_file, "a") as log:
        log.write(
            f"Step {step_num}: Ran operation '{operation}' with result {result} and saved to {output_path}\n"
        )


def run_steps_for_email(client, pipeline, timeout=10, log_file="execution.log"):
    email = client.email
    project = pipeline["project"]
    steps = pipeline["steps"]

    start_time = time.time()
    prev_datasite = None
    for step_num, step in enumerate(steps):
        if step["run"] != email:
            prev_datasite = step["run"]
            continue

        print("stepnum", step_num, step)
        while time.time() - start_time < timeout:
            try:
                prev_step_num = step_num - 1 if step_num > 0 else None
                execute_step(
                    client,
                    step,
                    email,
                    project,
                    step_num,
                    prev_step_num,
                    prev_datasite,
                    log_file,
                )
                print(f"Step {step_num} completed for {email}.")
                prev_datasite = email  # Update prev_datasite to current step's email
                break
            except Exception as e:
                print(
                    f"Step {step_num} for {email} failed with error: {e}. Retrying..."
                )
                time.sleep(1)  # Retry delay
        else:
            print(
                f"Timeout reached for step {step_num} for {email}. Check logs for details."
            )


def main():
    # Set up argument parser
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, help="Path to the Client Config")
    args = parser.parse_args()

    # Load the config path from the command-line argument
    config_path = args.config

    client = Client.load(config_path)
    print(client)

    # Load YAML configuration
    pipeline = load_yaml("./add.yaml")

    run_steps_for_email(client, pipeline, timeout=120, log_file=f"./{client.email}.log")


if __name__ == "__main__":
    main()
