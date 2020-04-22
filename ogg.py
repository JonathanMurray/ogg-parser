import os
from typing import List, Dict, Iterator, Optional

MAX_PARSED_PAGES = 100_000
DEBUG = False


def debug(label: str, message: str):
  if DEBUG:
    print("[%s]: %s" % (label, message))


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


class PageHeader:
  def __init__(self, version, header_type_flag, absolute_granule_position, stream_serial_number, page_sequence_number,
      page_checksum, segment_table, header_byte_length, packet_sizes, page_content_length):
    # Raw data found in the header
    self.version: int = version
    self.header_type_flag = header_type_flag
    self.absolute_granule_position: int = absolute_granule_position
    self.stream_serial_number: int = stream_serial_number
    self.page_sequence_number: int = page_sequence_number
    self.page_checksum: int = page_checksum
    self.segment_table: List[int] = segment_table

    # Derived from the segment table
    self.packet_sizes: List[int] = packet_sizes
    self.page_content_length: int = page_content_length

    # Byte length of the header
    self.header_byte_length: int = header_byte_length

  def __repr__(self):
    return "(Page %i in '%s'. %i packets)" \
           % (self.page_sequence_number, self.stream_serial_number, len(self.packet_sizes))


class Page:
  def __init__(self, page_header: PageHeader, byte_offset, header_byte_length, content_byte_length):
    self.header: PageHeader = page_header
    self.byte_offset: int = byte_offset
    self.header_byte_length: int = header_byte_length
    self.content_byte_length: int = content_byte_length

  def __repr__(self):
    return "(%s, offset: %i, header length: %i, content length: %i)" % \
           (self.header, self.byte_offset, self.header_byte_length, self.content_byte_length)


class VorbisPacket:
  pass


class AudioPacket(VorbisPacket):

  def __init__(self, packet_length):
    self.packet_length = packet_length

  def __repr__(self):
    return "Audio packet (length: %i)" % self.packet_length


class SetupHeaderPacket(VorbisPacket):

  def __init__(self, packet_length):
    self.packet_length = packet_length

  def __repr__(self):
    return "Setup header (length: %i)" % self.packet_length


class IdentificationHeaderPacket(VorbisPacket):
  def __init__(self, channels, sample_rate, bitrate_max, bitrate_nominal, bitrate_min, block_size_0_and_1,
      packet_length):
    self.channels: int = channels
    self.sample_rate: int = sample_rate
    self.bitrate_max: int = bitrate_max
    self.bitrate_nominal: int = bitrate_nominal
    self.bitrate_min: int = bitrate_min
    self.block_size_0_and_1: int = block_size_0_and_1
    self.packet_length: int = packet_length

  def __repr__(self):
    return "Identification header (%iHz, %i channel(s), %ikb/s, length: %i)" \
           % (self.sample_rate, self.channels, self.bitrate_nominal // 1000, self.packet_length)


class CommentHeaderPacket(VorbisPacket):
  def __init__(self, vendor, comments, packet_length):
    self.vendor: str = vendor
    self.comments: List[str] = comments
    self.packet_length: int = packet_length

  def __repr__(self):
    return "Comment header (vendor: %s, comments: %s, length: %i)" % (self.vendor, self.comments, self.packet_length)


class OggParser:

  def __init__(self):
    self.stream_parsers: Dict[int, StreamParser] = {}

  def parse_ogg_file(self, file) -> Iterator[Page]:
    log_tag = "parse_ogg_file()"

    current_page_header_offset = 0

    for page_index in range(MAX_PARSED_PAGES):

      page_header = self._parse_page_header(file)

      if page_header is None:
        # end of file
        return

      fresh_packet = page_header.header_type_flag & 1
      first_page_of_logical_bitstream = page_header.header_type_flag & 2
      last_page_of_logical_bitstream = page_header.header_type_flag & 4

      if fresh_packet:
        debug(log_tag, "fresh packet")
      if first_page_of_logical_bitstream:
        debug(log_tag,
              "Logical bitstream %s starting at page %i" % (page_header.stream_serial_number, page_index))
        self.stream_parsers[page_header.stream_serial_number] = StreamParser()
      if last_page_of_logical_bitstream:
        debug(log_tag,
              "Logical bitstream %s ending at page %i" % (page_header.stream_serial_number, page_index))
        stream_parser = self.stream_parsers[page_header.stream_serial_number]
        stream_parser.last_absolute_granule_position = page_header.absolute_granule_position

      # Here we hand over control to the consumer
      yield Page(page_header, current_page_header_offset, page_header.header_byte_length,
                 page_header.page_content_length)

      # Here we're back in control, so we seek to the start of the next page header
      current_page_header_offset += page_header.header_byte_length + page_header.page_content_length
      debug(log_tag, "Seeking to next page header. Offset: %i" % current_page_header_offset)
      file.seek(current_page_header_offset, os.SEEK_SET)

    print("ERROR: Processed %i pages without reaching end of file!" % MAX_PARSED_PAGES)

  @staticmethod
  def _parse_page_header(file) -> Optional[PageHeader]:

    log_tag = "_parse_page_header()"

    capture_pattern = read_bytes(file, 4)
    if capture_pattern == b'':
      debug(log_tag, "Reached end of file")
      return None
    if capture_pattern != b"OggS":
      raise Exception("Expected capture pattern but got: %s" % capture_pattern)
    version = read_i8(file)
    header_type_flag = read_i8(file)
    absolute_granule_position = read_i64(file)
    stream_serial_number = read_i32(file)
    page_sequence_number = read_i32(file)
    page_checksum = read_i32(file)
    num_page_segments = read_i8(file)
    bytes_read = 4 + 1 + 1 + 8 + 4 + 4 + 4 + 1

    segment_table = []

    page_content_length = 0
    packet_sizes = []
    packet_size_accumulator = 0

    for i in range(num_page_segments):
      lacing_value = read_i8(file)
      bytes_read += 1
      segment_table.append(lacing_value)

      page_content_length += lacing_value
      packet_size_accumulator += lacing_value
      if lacing_value < 255:
        packet_sizes.append(packet_size_accumulator)
        packet_size_accumulator = 0

    return PageHeader(version, header_type_flag, absolute_granule_position, stream_serial_number, page_sequence_number,
                      page_checksum, segment_table, bytes_read, packet_sizes, page_content_length)


def write_page_header(file, page_header: PageHeader):
  file.write(b"OggS")
  write_i8(file, page_header.version)
  write_i8(file, page_header.header_type_flag)
  write_i64(file, page_header.absolute_granule_position)
  write_i32(file, page_header.stream_serial_number)
  write_i32(file, page_header.page_sequence_number)
  write_i32(file, page_header.page_checksum)
  write_i8(file, len(page_header.segment_table))
  for lacing_value in page_header.segment_table:
    write_i8(file, lacing_value)


def write_identification_header_packet(file, header: IdentificationHeaderPacket):
  write_i8(file, 1)  # packet type == identification header
  write_bytes(file, b'vorbis')  # codec identifier
  write_i32(file, 0)  # vorbis_version
  write_i8(file, header.channels)
  write_i32(file, header.sample_rate)
  write_i32(file, header.bitrate_max)
  write_i32(file, header.bitrate_nominal)
  write_i32(file, header.bitrate_min)
  write_i8(file, 184)  # block_size_0 and block_size_1
  write_i8(file, 1)  # framing_flag


class StreamParser:
  def __init__(self):
    self.identification_header: Optional[IdentificationHeaderPacket] = None
    self.comment_header: Optional[CommentHeaderPacket] = None
    self.last_absolute_granule_position: Optional[int] = None
    self.num_packets_parsed: int = 0

  def __repr__(self):
    return "%s, %s, duration: %ss, parsed %i packets" \
           % (self.identification_header, self.comment_header, self.calculate_duration(), self.num_packets_parsed)

  def calculate_duration(self) -> Optional[float]:
    if self.last_absolute_granule_position is not None and self.identification_header is not None:
      return self.last_absolute_granule_position / self.identification_header.sample_rate

  def parse_page_content(self, file, content_byte_offset: int, packet_sizes: List[int]) -> Iterator[VorbisPacket]:
    log_tag = "parse_page_content()"
    debug(log_tag, "Parsing page content. Offset: %i" % content_byte_offset)

    file.seek(content_byte_offset, os.SEEK_SET)

    for packet_index, packet_size in enumerate(packet_sizes):
      yield self._parse_packet(file, packet_size)

    debug(log_tag, "Parsed page")

  def _parse_packet(self, file, packet_size) -> VorbisPacket:
    log_tag = "_parse_packet()"
    bytes_read = 0
    debug(log_tag, "Starting to parse packet")
    packet_type = read_i8(file)
    bytes_read += 1
    debug(log_tag, "packet_type: %s" % packet_type)
    if packet_type & 1 == 0:
      packet = self._parse_audio_packet(file, bytes_read, packet_size)
    else:
      codec_identifier = read_bytes(file, 6)
      bytes_read += 6
      if codec_identifier != b'vorbis':
        raise Exception("Unexpected codec identifier: %s" % codec_identifier)
      if packet_type == 1:
        packet = self._parse_identification_header(file, bytes_read)
        self.identification_header = packet
      elif packet_type == 3:
        packet = self._parse_comment_header(file, bytes_read)
        self.comment_header = packet
      elif packet_type == 5:
        packet = self._parse_setup_header(file, bytes_read, packet_size)
      else:
        raise Exception("Unexpected packet type: %s" % packet_type)
    if packet.packet_length != packet_size:
      raise Exception("Expected packet of length %i, but packet was %i bytes!" % (packet_size, packet.packet_length))
    debug(log_tag, "Parsed packet")
    self.num_packets_parsed += 1
    return packet

  @staticmethod
  def _parse_identification_header(file, bytes_read: int) -> IdentificationHeaderPacket:
    vorbis_version = read_i32(file)
    if vorbis_version != 0:
      raise Exception("Unsupported vorbis version: %s" % vorbis_version)

    channels = read_i8(file)
    sample_rate = read_i32(file)
    bitrate_max = read_i32(file)
    bitrate_nominal = read_i32(file)
    bitrate_min = read_i32(file)
    block_size_0_and_1 = read_i8(file)
    skip(file, 1)  # framing_flag

    packet_length = bytes_read + 4 + 1 + 4 + 4 + 4 + 4 + 1 + 1

    return IdentificationHeaderPacket(channels, sample_rate, bitrate_max, bitrate_nominal, bitrate_min,
                                      block_size_0_and_1, packet_length)

  @staticmethod
  def _parse_comment_header(file, bytes_read: int) -> CommentHeaderPacket:
    additional_bytes_read = 0
    vendor_length = read_i32(file)
    additional_bytes_read += 4
    vendor = read_str(file, vendor_length)
    additional_bytes_read += vendor_length
    user_comment_list_length = read_i32(file)
    additional_bytes_read += 4
    comments = []
    for i in range(user_comment_list_length):
      length = read_i32(file)
      additional_bytes_read += 4
      comment = read_str(file, length)
      additional_bytes_read += length
      comments.append(comment)
    comments = comments
    framing_bit = read_i8(file)
    additional_bytes_read += 1
    if framing_bit & 1 == 0:
      raise Exception("Framing bit should be set at the end of comment header!")
    return CommentHeaderPacket(vendor, comments, bytes_read + additional_bytes_read)

  @staticmethod
  def _parse_setup_header(file, bytes_read: int, packet_size):
    skip(file, packet_size - bytes_read)
    return SetupHeaderPacket(packet_size)

  @staticmethod
  def _parse_audio_packet(file, bytes_read: int, packet_size: int):
    skip(file, packet_size - bytes_read)
    return AudioPacket(packet_size)
