from __future__ import annotations  # to allow type references to self

import os
from typing import List, Dict, Iterator, Optional

from io_util import write_i8, write_i32, read_i32, read_i8, read_bytes, write_i64, read_i64
from vorbis import StreamParser

MAX_PARSED_PAGES = 100_000
DEBUG = True


def debug(label: str, message: str):
  if DEBUG:
    print("[%s]: %s" % (label, message))


class PageHeader:
  def __init__(self, version, fresh_packet, beginning_of_stream, end_of_stream, absolute_granule_position,
      stream_serial_number, page_sequence_number, page_checksum, segment_table, header_byte_length, packet_sizes,
      page_content_length):
    # Raw data found in the header
    self.version: int = version
    self.absolute_granule_position: int = absolute_granule_position
    self.stream_serial_number: int = stream_serial_number
    self.page_sequence_number: int = page_sequence_number
    self.page_checksum: int = page_checksum
    self.segment_table: List[int] = segment_table

    # Derived from the segment table
    self.packet_sizes: List[int] = packet_sizes
    self.page_content_length: int = page_content_length

    # Derived from header type flag
    self.fresh_packet = fresh_packet
    self.beginning_of_stream = beginning_of_stream
    self.end_of_stream = end_of_stream

    # Byte length of the header
    self.header_byte_length: int = header_byte_length

  @staticmethod
  def parse(file) -> Optional[PageHeader]:

    log_tag = "PageHeader._parse()"

    capture_pattern = read_bytes(file, 4)
    if capture_pattern == b'':
      debug(log_tag, "Reached end of file")
      return None
    if capture_pattern != b"OggS":
      raise Exception("Expected capture pattern but got: %s" % capture_pattern)
    version = read_i8(file)
    header_type_flag = read_i8(file)
    fresh_packet = header_type_flag & 1
    beginning_of_stream = header_type_flag & 2
    end_of_stream = header_type_flag & 4
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

    return PageHeader(version, fresh_packet, beginning_of_stream, end_of_stream, absolute_granule_position,
                      stream_serial_number, page_sequence_number,
                      page_checksum, segment_table, bytes_read, packet_sizes, page_content_length)

  def write_to_file(self, file):
    file.write(b"OggS")
    write_i8(file, self.version)
    header_type_flag = 0
    if self.fresh_packet:
      header_type_flag |= 1
    if self.beginning_of_stream:
      header_type_flag |= 2
    if self.end_of_stream:
      header_type_flag |= 4
    write_i8(file, header_type_flag)
    write_i64(file, self.absolute_granule_position)
    write_i32(file, self.stream_serial_number)
    write_i32(file, self.page_sequence_number)
    write_i32(file, self.page_checksum)
    write_i8(file, len(self.segment_table))
    for lacing_value in self.segment_table:
      write_i8(file, lacing_value)

  def copy(self) -> PageHeader:
    return PageHeader(
        self.version, self.fresh_packet, self.beginning_of_stream, self.end_of_stream, self.absolute_granule_position,
        self.stream_serial_number, self.page_sequence_number, self.page_checksum, self.segment_table,
        self.header_byte_length, self.packet_sizes, self.page_content_length)

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


class OggParser:

  def __init__(self):
    self.stream_parsers: Dict[int, StreamParser] = {}
    self.num_pages_parsed = 0

  def parse_ogg_file(self, file) -> Iterator[Page]:
    log_tag = "parse_ogg_file()"

    current_page_header_offset = 0

    for page_index in range(MAX_PARSED_PAGES):

      page_header = PageHeader.parse(file)

      if page_header is None:
        # end of file
        return

      if page_header.fresh_packet:
        debug(log_tag, "fresh packet")
      if page_header.beginning_of_stream:
        debug(log_tag,
              "Logical bitstream %s starting at page %i" % (page_header.stream_serial_number, page_index))
        self.stream_parsers[page_header.stream_serial_number] = StreamParser()
      if page_header.end_of_stream:
        debug(log_tag,
              "Logical bitstream %s ending at page %i" % (page_header.stream_serial_number, page_index))
        stream_parser = self.stream_parsers[page_header.stream_serial_number]
        stream_parser.last_absolute_granule_position = page_header.absolute_granule_position

      self.num_pages_parsed += 1

      # Here we hand over control to the consumer
      yield Page(page_header, current_page_header_offset, page_header.header_byte_length,
                 page_header.page_content_length)

      # Here we're back in control, so we seek to the start of the next page header
      current_page_header_offset += page_header.header_byte_length + page_header.page_content_length
      debug(log_tag, "Seeking to next page header. Offset: %i" % current_page_header_offset)
      file.seek(current_page_header_offset, os.SEEK_SET)

    print("ERROR: Processed %i pages without reaching end of file!" % MAX_PARSED_PAGES)
