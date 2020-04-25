#!/usr/bin/env python3
import sys

from ogg import OggParser


def get_duration(file_name: str):
  parser = OggParser()
  with open(file_name, "rb") as file:
    for i, page in enumerate(parser.parse_ogg_file(file)):
      content_offset = page.byte_offset + page.header_byte_length
      stream_parser = parser.stream_parsers[page.header.stream_serial_number]

      # The identification header packet contains the sample_rate which we need to calculate duration
      if stream_parser.identification_header is None:
        for _ in stream_parser.get_packets_in_page(file, content_offset, page.header.packet_sizes):
          pass

  for (stream_serial_number, stream_parser) in parser.stream_parsers.items():
    print(stream_parser.calculate_duration())


if __name__ == "__main__":
  if len(sys.argv) < 2:
    print("USAGE: %s inputfile" % sys.argv[0])
    sys.exit()
  file_name_arg = sys.argv[1]
  get_duration(file_name_arg)
