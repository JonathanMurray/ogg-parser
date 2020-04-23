# Ogg parser

This repository contains a small library for parsing Ogg files, as well as a few example 
command-line applications. It's intended mainly as a simple reference implementation for learning
purposes. 

Disclaimer: there is no support for advanced features, and there may be bugs. Contributions are
welcome!

## Try it out

### Get the duration of an Ogg Vorbis file:
`./get_duration.py <oggfile>`

This prints the duration to stdout as a floating number e.g. `161.30391666666668`

### Speed up / slow down an Ogg Vorbis file
`./multiply_sample_rate.py <inputfile> <outputfile> <multiplier>`

This produces a modified version of `<inputfile>` where the sample rate (as defined in the Vorbis
_identification header_) has been multiplied by the given number.

Outputting to stdout is also supported by setting `<outputfile>` to `-`.

Example:

`./multiply_sample_rate.py input.ogg - 1.5 | ffplay -`

This immediately starts playing `input.ogg` with `ffplay`, sped up and pitched up by 50%.
