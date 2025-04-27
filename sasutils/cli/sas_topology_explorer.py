from pathlib import Path
import pprint  # Import pprint for pretty-printing

def explore_sas_topology():
  topology = {"enclosures": {}, "block_devices": {}}

  enclosures_path = Path("/sys/class/enclosure")
  if enclosures_path.exists():
    for enc in enclosures_path.glob("*[0-9]"):
      enc_name = enc.name

      id_file = enc / "id"
      if id_file.exists():
        enclosure_id = id_file.read_text().strip()
      else:
        enclosure_id = enc_name

      if enclosure_id in topology["enclosures"]:
        if isinstance(topology["enclosures"][enclosure_id]["name"], list):
          topology["enclosures"][enclosure_id]["name"].append(enc_name)
        else:
          topology["enclosures"][enclosure_id]["name"] = [topology["enclosures"][enclosure_id]["name"], enc_name]

        if isinstance(topology["enclosures"][enclosure_id]["sys_path"], list):
          topology["enclosures"][enclosure_id]["sys_path"].append(str(enc.resolve()))
        else:
          topology["enclosures"][enclosure_id]["sys_path"] = [topology["enclosures"][enclosure_id]["sys_path"], str(enc.resolve())]
      else:
        topology["enclosures"][enclosure_id] = {
          "name": enc_name,
          "components": None,
          "slots": {},
          "sys_path": str(enc.resolve()),
        }

      components_file = enc / "components"
      if components_file.exists():
        topology["enclosures"][enclosure_id]["components"] = int(components_file.read_text().strip())

      for enc_subdir in enc.iterdir():
        slot_file = enc_subdir / "slot"
        if slot_file.exists():
          try:
            slot_num = int(slot_file.read_text().strip())
            device_dir = enc_subdir / "device"

            slot_status_file = enc_subdir / "status"
            slot_status = slot_status_file.read_text().strip() if slot_status_file.exists() else None

            slot_locate_file = enc_subdir / "locate"
            slot_locate = slot_locate_file.read_text().strip() if slot_locate_file.exists() else None

            slot_fault_file = enc_subdir / "fault"
            slot_fault = slot_fault_file.read_text().strip() if slot_fault_file.exists() else None

            topology["enclosures"][enclosure_id]["slots"][slot_num] = {
              "name": enc_subdir.name,
              "status": slot_status,
              "device": device_dir.exists(),
              "locate": slot_locate,
              "fault": slot_fault,
            }
          except Exception as e:
            print(f"Error reading {device_dir}: {e}")

  # Discover block devices
  block_path = Path("/sys/block")
  if block_path.exists():
    for dev in block_path.glob("*"):
      if dev.is_symlink() or dev.is_dir():
        dev_name = dev.name
        dev_sys_path = dev.resolve()
        device_info = {
          "sys_path": str(dev_sys_path)
        }

        vendor_file = dev_sys_path / "device/vendor"
        model_file = dev_sys_path / "device/model"
        serial_file = dev_sys_path / "device/serial"

        if vendor_file.exists():
          device_info["vendor"] = vendor_file.read_text().strip()
        if model_file.exists():
          device_info["model"] = model_file.read_text().strip()
        if serial_file.exists():
          device_info["serial"] = serial_file.read_text().strip()

        topology["block_devices"][dev_name] = device_info

  return topology

if __name__ == "__main__":
  data = explore_sas_topology()
  pp = pprint.PrettyPrinter(width=120, compact=True)
  pp.pprint((data))