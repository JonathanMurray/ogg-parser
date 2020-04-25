from __future__ import annotations  # to allow type references to self

import os
from typing import List, Iterator, Optional, Tuple

from io_util import read_str, read_i32, read_i8, skip, read_bytes
from io_util import write_i8, write_bytes, write_i32

DEBUG = True


def debug(label: str, message: str):
  if DEBUG:
    print("[%s]: %s" % (label, message))


class VorbisPacket:
  def __init__(self, packet_length):
    self.packet_length = packet_length


class AudioPacket(VorbisPacket):

  def __init__(self, packet_length):
    super().__init__(packet_length)

  def __repr__(self):
    return "Audio packet (length: %i)" % self.packet_length


class SetupHeaderPacket(VorbisPacket):

  def __init__(self, packet_length):
    super().__init__(packet_length)

  def __repr__(self):
    return "Setup header (length: %i)" % self.packet_length


class IdentificationHeaderPacket(VorbisPacket):
  def __init__(self, channels, sample_rate, bitrate_max, bitrate_nominal, bitrate_min, block_size_0_and_1,
      packet_length):
    super().__init__(packet_length)
    self.channels: int = channels
    self.sample_rate: int = sample_rate
    self.bitrate_max: int = bitrate_max
    self.bitrate_nominal: int = bitrate_nominal
    self.bitrate_min: int = bitrate_min
    self.block_size_0_and_1: int = block_size_0_and_1

  def write_to_file(self, file):
    write_i8(file, 1)  # packet type == identification header
    write_bytes(file, b'vorbis')  # codec identifier
    write_i32(file, 0)  # vorbis_version
    write_i8(file, self.channels)
    write_i32(file, self.sample_rate)
    write_i32(file, self.bitrate_max)
    write_i32(file, self.bitrate_nominal)
    write_i32(file, self.bitrate_min)
    write_i8(file, self.block_size_0_and_1)  # block_size_0 and block_size_1
    write_i8(file, 1)  # framing_flag

  def __repr__(self):
    return "Identification header (%iHz, %i channel(s), %ikb/s, length: %i)" \
           % (self.sample_rate, self.channels, self.bitrate_nominal // 1000, self.packet_length)


class CommentHeaderPacket(VorbisPacket):
  def __init__(self, vendor, comments, packet_length):
    super().__init__(packet_length)
    self.vendor: str = vendor
    self.comments: List[str] = comments

  def __repr__(self):
    return "Comment header (vendor: %s, comments: %s, length: %i)" % (self.vendor, self.comments, self.packet_length)


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

  def get_packets_in_page(self, file, content_byte_offset: int, packet_sizes: List[int]) \
      -> Iterator[Tuple[int, VorbisPacket]]:
    log_tag = "get_packets_in_page()"
    debug(log_tag, "Parsing page content. Offset: %i" % content_byte_offset)

    offset = content_byte_offset
    for packet_size in packet_sizes:
      file.seek(offset, os.SEEK_SET)
      yield offset, self._parse_packet(file, packet_size)
      offset += packet_size

    debug(log_tag, "Parsed page")

  def _parse_packet(self, file, packet_size: int) -> VorbisPacket:
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
        debug(log_tag, "identification header")
        packet = self._parse_identification_header(file, bytes_read)
        self.identification_header = packet
      elif packet_type == 3:
        debug(log_tag, "comment header")
        packet = self._parse_comment_header(file, bytes_read)
        self.comment_header = packet
      elif packet_type == 5:
        debug(log_tag, "setup header")
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
