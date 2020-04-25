def read_i64(file) -> int:
  return int.from_bytes(file.read(8), byteorder="little")


def write_i64(file, value: int):
  file.write(int.to_bytes(value, 8, byteorder="little"))


def read_i32(file) -> int:
  return int.from_bytes(file.read(4), byteorder="little")


def write_i32(file, value: int):
  file.write(int.to_bytes(value, 4, byteorder="little"))


def read_i8(file) -> int:
  return int.from_bytes(file.read(1), byteorder="little")


def write_i8(file, value: int):
  file.write(int.to_bytes(value, 1, byteorder="little"))


def read_str(f, n_bytes: int) -> str:
  return f.read(n_bytes).decode("utf-8")


def read_bytes(file, n_bytes: int) -> bytes:
  return file.read(n_bytes)


def write_bytes(file, content: bytes):
  file.write(content)


def skip(file, n_bytes: int):
  file.read(n_bytes)
