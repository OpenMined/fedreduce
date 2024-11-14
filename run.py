import os
import traceback
import argparse
import time
import yaml
import logging
from typing import Tuple
from syftbox.lib import Client, SyftPermission
from sdk import StaticPipe, FilePipe

import copy
import re


# Set up logging configuration
import os
import json
import logging
from datetime import datetime


def find_first_yaml_file(directory):
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(".yaml"):
                return os.path.join(root, file)
    return None


# Set up logging configuration with JSON output
def setup_logger(log_file):
    logger = logging.getLogger("pipeline_logger")
    logger.setLevel(logging.DEBUG)

    # Console handler for printing to stdout
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)

    # File handler for writing to the log file in JSON format
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)

    # JSON Formatter
    class JsonFormatter(logging.Formatter):
        def format(self, record):
            log_record = {
                "timestamp": datetime.utcfromtimestamp(record.created).isoformat(),
                "message": record.getMessage(),
            }
            return json.dumps(log_record)

    # Set the JSON formatter for file logging
    json_formatter = JsonFormatter()
    file_handler.setFormatter(json_formatter)

    # Standard formatter for console output
    standard_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    console_handler.setFormatter(standard_formatter)

    # Add handlers to the logger
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    return logger


def load_yaml(file_path):
    with open(file_path, "r") as file:
        return yaml.safe_load(file)


def process_template(path_template, context):
    """Replaces placeholders in path templates with values from the context."""
    return path_template.format(**context)


def add(**kwargs):
    print("Calling add with arguments: %s", kwargs)
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


def execute_step(client, step, context, logger) -> bool:
    try:
        inputs = {}
        for input_item in step["inputs"]:
            key, pipe_config = next(iter(input_item.items()))
            inputs[key] = instantiate_pipe(client, pipe_config, context)

        if not all(pipe.ready() for pipe in inputs.values()):
            message = f"Inputs not ready for {step}."
            logger.debug(message)
            return False

        operation = step["function"]
        if operation == "add":
            result = add(**inputs)
        print("pipe", step["output"]["path"])
        output_pipe = instantiate_pipe(client, step["output"]["path"], context)
        folder = os.path.dirname(output_pipe.file_path)
        os.makedirs(folder, exist_ok=True)
        output_pipe.write(result)

        access_emails = [client.email]
        for emails in step["output"]["permissions"].get("read", []):
            print("email", emails, type(emails))
            if isinstance(emails, str):
                emails = [emails]

            for email in emails:
                access_email = process_template(email, context)
                access_emails.append(access_email)

        permission = SyftPermission(
            admin=access_emails, read=access_emails, write=access_emails
        )
        permission.ensure(folder)

        logger.info(
            "Ran operation '%s' with result %s and saved to %s",
            operation,
            result,
            output_pipe.file_path,
        )
        return True

    except Exception as e:
        logger.error("An error occurred during execute_step: %s", e)
        traceback.print_exc()
        raise e


def get_step_by_name(steps, name):
    """Finds the step configuration by its name."""
    for step in steps:
        if name in step:
            return step
    return None


def run_steps_for_email(client, pipeline, log_file, timeout=10):
    try:
        logger = setup_logger(log_file)
        email = client.email
        project = pipeline["project"]
        datasites = pipeline["workflow"]["datasites"]
        steps = pipeline["steps"]

        # Retrieve step configurations by name
        first_step_config = get_step_by_name(steps, "first")
        foreach_step_config = get_step_by_name(steps, "foreach")
        last_step_config = get_step_by_name(steps, "last")
        print("last_step_config", last_step_config)

        start_time = time.time()

        print("datasites", datasites, len(datasites))

        for step_num, datasite in enumerate(datasites):
            logger.info("Running step %d for %s.", step_num, email)
            if datasite != email:
                print("SKIPPING STEP", step_num, datasite, email)
                logger.info("Skipping step %d for other datasite.", step_num, email)
                continue
            print("RUNNING STEP", step_num, datasite, email)
            print("type", type(pipeline["author"]))
            context = {
                "author": pipeline["author"],
                "datasite": datasite,
                "project": project,
                "step": step_num,
                "prev_step": step_num - 1 if step_num > 0 else len(datasites) - 1,
                "next_step": (step_num + 1) % len(datasites),
                "prev_datasite": datasites[step_num - 1]
                if step_num > 0
                else datasites[-1],
                "next_datasite": datasites[(step_num + 1) % len(datasites)],
            }

            if step_num == 0 and first_step_config:
                print(">>>> FIRST STEP")
                step_config = copy.deepcopy(foreach_step_config)
                first_step_config = first_step_config["first"]
                print("first_step_config", first_step_config)

                if "inputs" in first_step_config:
                    first_inputs_dict = {
                        k: v
                        for item in first_step_config["inputs"]
                        for k, v in item.items()
                    }
                    foreach_inputs_dict = {
                        k: v for item in step_config["inputs"] for k, v in item.items()
                    }
                    merged_inputs_dict = {**foreach_inputs_dict, **first_inputs_dict}
                    step_config["inputs"] = [
                        {k: v} for k, v in merged_inputs_dict.items()
                    ]

            elif (step_num == len(datasites) - 1) and last_step_config:
                print(">>>> LAST STEP")
                logger.info("Running final step for %s", email)
                step_config = copy.deepcopy(foreach_step_config)
                last_step_config = last_step_config["last"]
                print("last_step_config", last_step_config)
                print("items", last_step_config["output"].items())
                print("step config", step_config["output"])
                if "output" in last_step_config:
                    # Extract last step's output configuration directly as a dictionary
                    last_output_dict = {
                        k: v for k, v in last_step_config["output"].items()
                    }

                    # Extract foreach step's output configuration directly as a dictionary
                    foreach_output_dict = step_config["output"]

                    # Merge the dictionaries
                    step_config["output"] = {**foreach_output_dict, **last_output_dict}
            else:
                step_config = foreach_step_config

            while time.time() - start_time < timeout:
                try:
                    print("tryying to execute step", step_config)
                    success = execute_step(client, step_config, context, logger)
                    if success:
                        logger.info("Step %d complete for %s.", step_num, email)
                        break
                    time.sleep(1)
                except Exception as e:
                    logger.error(
                        "Step %d for %s failed with error: %s. Retrying...",
                        step_num,
                        email,
                        e,
                    )
                    time.sleep(1)
            else:
                logger.error(
                    "Timeout reached for step %d for %s. Check logs for details.",
                    step_num,
                    email,
                )
    except Exception as e:
        logger.error("An error occurred during run_steps_for_email: %s", e)
        logger.debug("Traceback:\n%s", traceback.format_exc())  # Full traceback
        print("Traceback:\n%s", traceback.format_exc())  # Full traceback
        raise e


def check_done(client, pipeline, project, log_file, timeout=10) -> Tuple[bool, bool]:
    try:
        logger = setup_logger(log_file)
        email = client.email
        author = pipeline["author"]

        is_author = email == author
        if is_author:
            project = pipeline["project"]
            print(pipeline)

            complete = pipeline["complete"]
            exists_pipe_conf = complete["exists"]

            context = {
                "author": pipeline["author"],
                "datasite": email,
                "project": project,
            }
            print("got the complete condiction", complete, exists_pipe_conf)
            exists_pipe = instantiate_pipe(client, exists_pipe_conf, context)
            print("exists_pipe")
            print("exists_pipe", exists_pipe.ready())
            return exists_pipe.ready(), is_author
        else:
            complete_project_path = (
                client.sync_folder
                / project["author"]
                / "public"
                / "fedreduce"
                / "complete"
                / project["api_name"]
            )

            complete = os.path.exists(complete_project_path) and find_first_yaml_file(
                complete_project_path
            )
            return complete, False
    except Exception as e:
        logger.error("An error occurred during run_steps_for_email: %s", e)
        logger.debug("Traceback:\n%s", traceback.format_exc())  # Full traceback
        print("Traceback:\n%s", traceback.format_exc())  # Full traceback
        raise e
