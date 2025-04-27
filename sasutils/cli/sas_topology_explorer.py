from pathlib import Path
import pprint  # Import pprint for pretty-printing

def explore_sas_topology():
  topology = {}

  enclosures_path = Path("/sys/class/enclosure")
  if enclosures_path.exists():
    for enc in enclosures_path.glob("*[0-9]"):
      enc_name = enc.name

      id_file = enc / "id"
      if id_file.exists():
        enclosure_id = id_file.read_text().strip()
      else:
        enclosure_id = enc_name

      if enclosure_id in topology:
        # If already exists, append enc_name to name list
        if isinstance(topology[enclosure_id]["name"], list):
          topology[enclosure_id]["name"].append(enc_name)
        else:
          topology[enclosure_id]["name"] = [topology[enclosure_id]["name"], enc_name]

        if isinstance(topology[enclosure_id]["path"], list):
          topology[enclosure_id]["path"].append(str(enc.resolve()))
        else:
          topology[enclosure_id]["path"] = [topology[enclosure_id]["path"], str(enc.resolve())]
      else:
        topology[enclosure_id] = {
          "name": enc_name,
          "components": None,
          "slots": {},
          "path": str(enc.resolve()),
        }

        components_file = enc / "components"
        if components_file.exists():
          topology[enclosure_id]["components"] = int(components_file.read_text().strip())
  
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
  
              topology[enclosure_id]["slots"][slot_num] = {
                "name": enc_subdir.name,
                "status": slot_status,
                "device": device_dir.exists(),
                "locate": slot_locate,
                "fault": slot_fault,
              }
            except Exception as e:
              print(f"Error reading {device_dir}: {e}")

  expanders_path = Path("/sys/class/sas_expander")
  expanders = {}
  if expanders_path.exists():
    for exp in expanders_path.glob("*[0-9]"):
      exp_name = exp.name
      ports = []
      try:
        for port_dir in (exp / "device" / "port").glob("*"):
          try:
            attached_sas_addr_file = port_dir / "attached_sas_address"
            if attached_sas_addr_file.exists():
              attached_addr = attached_sas_addr_file.read_text().strip()
              ports.append(attached_addr)
          except Exception:
            continue
      except Exception:
        continue
      expanders[exp_name] = ports

  return {"enclosures": topology}

if __name__ == "__main__":
  data = explore_sas_topology()
  pp = pprint.PrettyPrinter(width=120, compact=True, sort_dicts=True)
  pp.pprint((data))
