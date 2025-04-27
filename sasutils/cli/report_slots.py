#!/usr/bin/env python3

import argparse
import sys
from sasutils.scsi import EnclosureDevice
from sasutils.sysfs import sysfs, SysfsObject
import pprint  # Import pprint for pretty-printing


class CustomPrettyPrinter(pprint.PrettyPrinter):
  """Custom PrettyPrinter to format dictionary values on the next line."""
  def _format(self, obj, stream, indent, allowance, context, level):
    if isinstance(obj, dict):
      # Print dictionaries with each key on its own line, values indented
      stream.write("{\n")
      for i, (key, value) in enumerate(obj.items()):
        stream.write(" " * (indent + self._indent_per_level))
        self._format(key, stream, indent + self._indent_per_level, allowance + 1, context, level)
        stream.write(":\n")
        stream.write(" " * (indent + 2 * self._indent_per_level))
        self._format(value, stream, indent + 2 * self._indent_per_level, allowance if i == len(obj) - 1 else 1, context, level)
        stream.write(",\n" if i < len(obj) - 1 else "\n")
      stream.write(" " * indent + "}")
    else:
      # Use the default formatting for other types
      super()._format(obj, stream, indent, allowance, context, level)



def _init_argparser():
  """Initialize argument parser for the CLI."""
  desc = 'CLI to report occupied slots in all enclosures.'
  parser = argparse.ArgumentParser(description=desc)
  parser.add_argument('-d', '--debug', action="store_true",
            help='Enable debugging output.')
  parser.add_argument('-j', '--json', action="store_true",
            help='Output results in JSON format.')
  return parser.parse_args()


def report_slots():
  """Report occupied slots in all enclosures."""
  args = _init_argparser()

  if args.debug:
    print("Debugging enabled.", file=sys.stderr)

  enclosures = []
  for node in sysfs.node('class').node('enclosure'):
    try:
      # Get the enclosure device
      enclosure = SysfsObject(node)
      slot_status_dict = {}  # Dictionary to group slots by their status

      # Iterate over child nodes to find valid slots
      for child_node in node:
        try:
          # Check if the node has a 'type' attribute with value 'array device'
          if child_node.get('type', None, True) == 'array device':
            slot_status = child_node.get('status', 'unknown')
            slot_device = child_node.node('device', 'missing')
            if slot_device != 'missing':
              slot_status += "_device"
            else:
              slot_status += "_missing"
            # Add the slot to the appropriate status list
            slot_status_dict.setdefault(slot_status, []).append(str(child_node))
        except Exception as e:
          if args.debug:
            print(f"Error processing slot node {child_node}: {e}", file=sys.stderr)

      enclosures.append({
        'enclosure': enclosure,
        'slots_by_status': slot_status_dict
      })
    except Exception as e:
      if args.debug:
        print(f"Error processing enclosure: {e}", file=sys.stderr)

  # Output results
  if args.json:
    import json
    print(json.dumps(enclosures, indent=4))
  else:
    # Use the custom PrettyPrinter
    pp = CustomPrettyPrinter(indent=2, width=80, compact=True, sort_dicts=True)
    pp.pprint(enclosures)
def main():
  """Entry point for the CLI."""
  try:
    report_slots()
  except Exception as e:
    print(f"Error: {e}", file=sys.stderr)
    sys.exit(1)


if __name__ == '__main__':
  main()