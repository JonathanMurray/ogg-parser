#!/usr/bin/env python3
import sys

from ogg import OggParser


def print_comments(file_name: str):
  parser = OggParser()
  with open(file_name, "rb") as file:
    for i, page in enumerate(parser.parse_ogg_file(file)):
      content_offset = page.byte_offset + page.header_byte_length
      stream_parser = parser.stream_parsers[page.header.stream_serial_number]

      if stream_parser.comment_header is None:
        for _ in stream_parser.get_packets_in_page(file, content_offset, page.header.packet_sizes):
          pass

  for stream_parser in parser.stream_parsers.values():
    print("Vendor: %s" % stream_parser.comment_header.vendor)
    for comment in stream_parser.comment_header.comments:
      print(comment)


if __name__ == "__main__":
  if len(sys.argv) < 2:
    print("USAGE: %s inputfile" % sys.argv[0])
    sys.exit()
  file_name_arg = sys.argv[1]
  print_comments(file_name_arg)
