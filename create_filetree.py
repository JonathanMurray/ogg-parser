#!/usr/bin/env python3
import shutil
import sys
from pathlib import Path

from ogg import OggParser

OUTDIR = Path("outdir")


def create_filetree(file_name: str):
  shutil.rmtree(OUTDIR)
  OUTDIR.mkdir()
  parser = OggParser()
  with open(file_name, "rb") as file:
    for i, page in enumerate(parser.parse_ogg_file(file)):
      page_dir = Path(OUTDIR, "%i" % i)
      page_dir.mkdir()
      Path(page_dir, "granule_pos=%i" % page.header.absolute_granule_position).touch()
      stream_parser = parser.stream_parsers[page.header.stream_serial_number]
      content_offset = page.byte_offset + page.header_byte_length
      for packet_index, (offset, packet) in enumerate(stream_parser.get_packets_in_page(file, content_offset,
                                                                                        page.header.packet_sizes)):
        packet_dir = Path(page_dir, "%i" % packet_index)
        packet_dir.mkdir()
        Path(packet_dir, "type=%s" % packet.__class__.__name__).touch()
        Path(packet_dir, "offset=%i" % offset).touch()


if __name__ == "__main__":
  if len(sys.argv) < 2:
    print("USAGE: %s inputfile" % sys.argv[0])
    sys.exit()
  file_name_arg = sys.argv[1]
  create_filetree(file_name_arg)
