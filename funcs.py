def map_reduce(file1_path, file2_path, transformer, operation):
    try:
        data1 = transformer(file1_path)
        data2 = transformer(file2_path)

        return operation(data1, data2)

    except FileNotFoundError as e:
        print(f"Error: {e}")
        return None
    except ValueError as e:
        print(f"Error: Could not convert file content - {e}")
        return None


def int_transformer(file_path):
    with open(file_path, "r") as file:
        return int(file.read().strip())


def add(x, y):
    return x + y


def multiply(x, y):
    return x * y
