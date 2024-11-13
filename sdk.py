import os
import json
import shutil
from typing import List, Optional, Tuple
from pathlib import Path
import hashlib
from syftbox.lib import Client


class Pipe:
    def read(self):
        """Reads data from the source."""
        raise NotImplementedError(
            "Subclasses or instances must implement the read method."
        )

    def write(self, data):
        """Writes data to the destination."""
        raise NotImplementedError(
            "Subclasses or instances must implement the write method."
        )

    def ready(self) -> bool:
        """Check if the pipe is ready to be read from or written to."""
        raise NotImplementedError(
            "Subclasses or instances must implement the ready method."
        )


class FilePipe(Pipe):
    def __init__(self, file_path):
        """Initializes the FilePipe with a specific file path."""
        self.file_path = file_path

    @classmethod
    def create(cls, file_path, initial_value=0):
        """Creates a FilePipe instance, initializing the file with an initial value if provided.

        Ensures that any necessary directories are created.
        """
        # Ensure the directory exists
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        # Initialize the file with the initial value
        instance = cls(file_path)
        instance.write(initial_value)
        return instance

    def read(self):
        """Reads and returns integer data from the file."""
        try:
            with open(self.file_path, "r") as file:
                data = int(file.read().strip())  # Assumes integer data for simplicity
            return data
        except FileNotFoundError:
            print(f"Error: The file {self.file_path} was not found.")
            return None
        except ValueError:
            print(
                f"Error: The file {self.file_path} does not contain valid integer data."
            )
            return None

    def write(self, data):
        """Writes integer data to the file as a string."""
        try:
            with open(self.file_path, "w") as file:
                file.write(str(data))
        except IOError as e:
            print(f"Error: Could not write to file {self.file_path} - {e}")

    def ready(self) -> bool:
        """Check if the file is ready to be read from or written to."""
        return os.path.exists(self.file_path)


class StaticPipe(Pipe):
    def __init__(self, initial_value=0):
        """Initializes the StaticPipe with an initial static value."""
        self.value = initial_value

    def read(self):
        """Returns the current static value."""
        return self.value

    def write(self, data):
        """Sets a new value, allowing accumulation or updating."""
        self.value = data

    def ready(self) -> bool:
        """Check if the static value is ready to be read from or written to."""
        return True


def map_reduce(input_pipe_1, input_pipe_2, operation, output_pipe):
    try:
        # Use input pipes to read and transform data
        data1 = input_pipe_1.read()
        data2 = input_pipe_2.read()

        # Ensure both data inputs are valid before proceeding
        if data1 is None or data2 is None:
            return None

        # Perform the operation on the transformed data
        result = operation(data1, data2)

        # Use output pipe to write the result
        output_pipe.write(result)

        return result

    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return None


class Settings:
    def __init__(self, filename="./settings.json"):
        self.filename = filename
        self.data = self._load()

    def _load(self):
        if os.path.exists(self.filename):
            with open(self.filename, "r") as file:
                try:
                    return json.load(file)
                except json.JSONDecodeError:
                    return {}
        return {}

    def save(self):
        with open(self.filename, "w") as file:
            json.dump(self.data, file, indent=4)

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value
        self.save()

    def delete(self, key):
        if key in self.data:
            del self.data[key]
            self.save()

    def all(self):
        return self.data


def extract_datasite(path: str) -> Optional[str]:
    right = str(path).split("datasites/")
    datasite = right[1].split("/")[0]
    if "@" in datasite:
        return datasite
    return None


def datasites_file_glob(client: Client, pattern: str) -> List[Tuple[str, Path]]:
    datasites = Path(f"{client.sync_folder}")
    # fixes change in client paths
    if "datasites" not in str(datasites):
        datasites = datasites / "datasites"

    matches = datasites.glob(pattern)
    results = []
    for path in matches:
        datasite = extract_datasite(path)
        if datasite:
            results.append((datasite, path))
    return results


def public_url(path: str) -> Optional[str]:
    path = str(path)
    public_path = path.split("public")[-1]
    datasite = extract_datasite(path)
    if "public" not in path:
        return None
    public_path = f"/{public_path}".replace("//", "/")
    return f"https://syftbox.openmined.org/datasites/{datasite}{public_path}"


def calculate_file_hash(file_path, hash_func=hashlib.sha256):
    """Calculate the hash of a file."""
    hash_obj = hash_func()
    with open(file_path, "rb") as f:
        while chunk := f.read(8192):
            hash_obj.update(chunk)
    return hash_obj.hexdigest()


def ensure(files, destination_folder):
    """Ensure that specified files are in the destination folder with the same
    hashes. If the destination folder doesn't exist, create it.
    Copy files if missing or hashes differ."""

    # Ensure destination folder exists
    Path(destination_folder).mkdir(parents=True, exist_ok=True)

    for src_file_path in files:
        # Check if the source file exists
        if not os.path.exists(src_file_path):
            print(f"Source file '{src_file_path}' does not exist.")
            continue

        file_name = os.path.basename(src_file_path)
        dest_file_path = os.path.join(destination_folder, file_name)

        # Calculate the hash of the source file
        src_hash = calculate_file_hash(src_file_path)

        # Check if destination file exists and has the same hash
        if os.path.exists(dest_file_path):
            dest_hash = calculate_file_hash(dest_file_path)
            if src_hash == dest_hash:
                print(f"File '{file_name}' is up-to-date.")
                continue  # Skip copying as the file is the same

        # Copy file from source to destination
        shutil.copy2(src_file_path, dest_file_path)
        print(f"Copied '{file_name}' to '{dest_file_path}'.")
