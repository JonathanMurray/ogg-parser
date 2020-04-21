#!/usr/bin/env python3
import sys

import ogg
from ogg import OggParser, IdentificationHeaderPacket


def multiply_sample_rate(input_file_name: str, output_file_name: str, multiplier: float):
  parser = OggParser()
  with open(input_file_name, "rb") as input_file:
    if output_file_name != '-':
      output_file = open(output_file_name, "wb")
    else:
      output_file = sys.stdout.buffer
    try:
      has_written_identification_header = False
      for i, page in enumerate(parser.parse_ogg_file(input_file)):
        content_offset = page.byte_offset + page.header_byte_length
        stream_parser = parser.stream_parsers[page.header.stream_serial_number]

        ogg.write_page_header(output_file, page.header)

        if has_written_identification_header:
          # We have already written the important header. Just copy page blindly now
          page_content = ogg.read_bytes(input_file, page.content_byte_length)
          ogg.write_bytes(output_file, page_content)

        # parse packets until we have found the identification header
        if stream_parser.identification_header is None:
          for packet in stream_parser.parse_page_content(input_file, content_offset, page.header.packet_sizes):
            if isinstance(packet, IdentificationHeaderPacket):
              rewritten_packet = IdentificationHeaderPacket(
                  packet.channels, int(packet.sample_rate * multiplier), packet.bitrate_max, packet.bitrate_nominal,
                  packet.bitrate_min, packet.block_size_0_and_1, packet.packet_length)
              ogg.write_identification_header_packet(output_file, rewritten_packet)
              has_written_identification_header = True
            else:
              raise Exception("Got unexpected packet: %s" % packet)
    finally:
      output_file.close()


if __name__ == "__main__":
  if len(sys.argv) < 3:
    print("USAGE: %s inputfile outputfile [multiplier]\nSetting the outputfile arg to - writes the output to stdout" %
          sys.argv[0])
    sys.exit()
  in_file_name = sys.argv[1]
  out_file_name = sys.argv[2]
  if len(sys.argv) == 4:
    mult = float(sys.argv[3])
  else:
    mult = 2
  multiply_sample_rate(in_file_name, out_file_name, mult)
