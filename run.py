import os
import traceback
import argparse
import time
import yaml
from syftbox.lib import Client, SyftPermission
from sdk import StaticPipe, FilePipe

import copy
import re


def load_yaml(file_path):
    with open(file_path, "r") as file:
        return yaml.safe_load(file)


def process_template(path_template, context):
    """Replaces placeholders in path templates with values from the context."""
    return path_template.format(**context)


def add(**kwargs):
    # Perform addition on all provided inputs by reading their values
    # Assumes each input is a pipe with a `read()` method.
    result = sum(input_pipe.read() for input_pipe in kwargs.values())
    return result


def instantiate_pipe(client, pipe_config, context):
    """Instantiates StaticPipe or FilePipe based on YAML configuration."""

    if isinstance(pipe_config, dict):
        # Unpack the nested structure for class instantiation
        if "StaticPipe" in pipe_config:
            value = pipe_config["StaticPipe"]
            return StaticPipe(value)
        elif "FilePipe" in pipe_config:
            value = pipe_config["FilePipe"]
            file_path = process_template(value, context)
            return FilePipe(client.sync_folder / file_path)

    elif isinstance(pipe_config, str):
        # Check if pipe_config is in the form "FilePipe(...)" or "StaticPipe(...)"
        file_pipe_match = re.match(r'FilePipe\("(.+)"\)', pipe_config)
        static_pipe_match = re.match(r"StaticPipe\((.+)\)", pipe_config)

        if file_pipe_match:
            # Extract the path inside the FilePipe() syntax
            path_template = file_pipe_match.group(1)
            file_path = process_template(path_template, context)
            return FilePipe(client.sync_folder / file_path)

        elif static_pipe_match:
            # Extract the value inside StaticPipe() and convert it to the correct type
            static_value = static_pipe_match.group(1)
            # Attempt to parse as int or float if possible, otherwise keep as a string
            try:
                static_value = int(static_value)
            except ValueError:
                try:
                    static_value = float(static_value)
                except ValueError:
                    pass  # Keep as string if it can't be converted
            return StaticPipe(static_value)

    # If none of the cases match, raise an error
    raise ValueError(f"Invalid pipe configuration: {pipe_config}")


def execute_step(client, step, context, log_file) -> bool:
    try:
        # Process inputs dynamically, allowing for arbitrary keys
        inputs = {}
        for input_item in step["inputs"]:
            # Each `input_item` will have one key, so we extract it dynamically
            key, pipe_config = next(iter(input_item.items()))
            inputs[key] = instantiate_pipe(client, pipe_config, context)

        if not all(pipe.ready() for pipe in inputs.values()):
            message = f"Inputs not ready for {step}.\n"
            print(message)
            with open(log_file, "a") as log:
                log.write(message)
            return False

        # Perform operation
        operation = step["function"]
        if operation == "add":
            # Call the add function with all inputs as keyword arguments
            result = add(**inputs)

        # Process output
        output_pipe = instantiate_pipe(client, step["output"]["path"], context)
        print("output path", output_pipe)

        folder = os.path.dirname(output_pipe.file_path)
        os.makedirs(folder, exist_ok=True)
        output_pipe.write(result)

        # Set permissions
        access_emails = [client.email]
        for email in step["output"]["permissions"].get("read", []):
            access_email = process_template(email, context)
            access_emails.append(access_email)

        permission = SyftPermission(
            admin=access_emails, read=access_emails, write=access_emails
        )
        permission.ensure(folder)

        # Log the step execution
        with open(log_file, "a") as log:
            message = f"Ran operation '{operation}' with result {result} and saved to {output_pipe.file_path}\n"
            log.write(message)
            print(message)
        return True

    except Exception as e:
        # Print the full traceback to help identify the exact line of the error
        print(f"An error occurred during execute_step: {e}")
        traceback.print_exc()  # This prints the full traceback to the console
        raise e


def run_steps_for_email(client, pipeline, timeout=10, log_file="execution.log"):
    email = client.email
    project = pipeline["project"]
    datasites = pipeline["workflow"]["datasites"]
    steps = pipeline["steps"]

    # Check for optional `first` configuration
    first_step_config = steps[0].get("first")
    foreach_step_config = steps[1]

    start_time = time.time()

    for step_num, datasite in enumerate(datasites):
        # Prepare the context for placeholders
        context = {
            "datasite": datasite,
            "project": project,
            "step": step_num,
            "prev_step": step_num - 1 if step_num > 0 else len(datasites) - 1,
            "next_step": (step_num + 1) % len(datasites),
            "prev_datasite": datasites[step_num - 1] if step_num > 0 else datasites[-1],
            "next_datasite": datasites[(step_num + 1) % len(datasites)],
        }

        # Determine which configuration to use for the step
        print("A", step_num, first_step_config)
        if step_num == 0 and first_step_config:
            print("fdsafdsa")
            # Start with a deep copy of the `foreach` configuration
            step_config = copy.deepcopy(foreach_step_config)

            # Merge `first` inputs to override specific values in `foreach`
            if "inputs" in first_step_config:
                first_inputs_dict = {
                    k: v
                    for item in first_step_config["inputs"]
                    for k, v in item.items()
                }
                foreach_inputs_dict = {
                    k: v for item in step_config["inputs"] for k, v in item.items()
                }
                print("first_inputs_dict", first_inputs_dict)
                # Override the inputs in `foreach` with those in `first`
                merged_inputs_dict = {**foreach_inputs_dict, **first_inputs_dict}
                print("merged_inputs_dict", merged_inputs_dict)
                step_config["inputs"] = [{k: v} for k, v in merged_inputs_dict.items()]
                print("step_config", step_config)
        else:
            print("ELSE")
            # Use `foreach` step configuration directly
            step_config = foreach_step_config

        # Check if this step should be run by the current client
        if datasite != email:
            print(f"Skipping step {step_num} for other datasite.")
            continue

        # Execute the step
        while time.time() - start_time < timeout:
            try:
                success = execute_step(client, step_config, context, log_file)
                if success:
                    print(f"Step {step_num} completed for {email}.")
                    break
                time.sleep(1)
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

    # Load the client configuration
    config_path = args.config
    client = Client.load(config_path)
    print(client)

    # Load YAML configuration
    pipeline = load_yaml("./add.yaml")

    # Run steps for the client
    run_steps_for_email(client, pipeline, timeout=120, log_file=f"./{client.email}.log")


if __name__ == "__main__":
    main()
