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


import os


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
