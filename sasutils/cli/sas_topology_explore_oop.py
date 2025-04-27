from pathlib import Path
import pprint

class Slot:
  def __init__(self, path):
    self.path = Path(path)
    self.name = self.path.name
    self.slot_num = self._read_int("slot")
    self.device = (self.path / "device").exists()
    self.status = self._read_text("status")
    self._locate = self._read_text("locate")
    self._fault = self._read_text("fault")

  def _read_text(self, field):
    file = self.path / field
    return file.read_text().strip() if file.exists() else None

  def _read_int(self, field):
    file = self.path / field
    return int(file.read_text().strip()) if file.exists() else None

  @property
  def locate(self):
    return self._locate

  @locate.setter
  def locate(self, value):
    file = self.path / "locate"
    if file.exists():
      file.write_text(str(value))
    self._locate = str(value)

  @property
  def fault(self):
    return self._fault

  @fault.setter
  def fault(self, value):
    file = self.path / "fault"
    if file.exists():
      file.write_text(str(value))
    self._fault = str(value)

class Enclosure:
  def __init__(self, path):
    self.path = Path(path)
    self.name = self.path.name
    self.id = self._read_text("id") or self.name
    self.sys_path = str(self.path.resolve())
    self.components = self._read_int("components")
    self.slots = {}
    self._load_slots()

  def _read_text(self, field):
    file = self.path / field
    return file.read_text().strip() if file.exists() else None

  def _read_int(self, field):
    file = self.path / field
    return int(file.read_text().strip()) if file.exists() else None

  def _load_slots(self):
    for subdir in self.path.iterdir():
      if (subdir / "slot").exists():
        slot = Slot(subdir)
        self.slots[slot.slot_num] = slot

class BlockDevice:
  def __init__(self, path):
    self.path = Path(path)
    self.name = self.path.name
    self.sys_path = str(self.path.resolve())
    self.vendor = self._read_text("device/vendor")
    self.model = self._read_text("device/model")
    self.serial = self._read_text("device/serial")

  def _read_text(self, relative_path):
    file = self.path / relative_path
    return file.read_text().strip() if file.exists() else None

def explore_sas_topology():
  topology = {"enclosures": {}, "block_devices": {}}

  enclosures_path = Path("/sys/class/enclosure")
  if enclosures_path.exists():
    for enc in enclosures_path.glob("*"):
      if enc.is_dir():
        enclosure = Enclosure(enc)
        topology["enclosures"][enclosure.id] = enclosure

  block_path = Path("/sys/block")
  if block_path.exists():
    for dev in block_path.glob("*"):
      if dev.is_symlink() or dev.is_dir():
        block_device = BlockDevice(dev)
        topology["block_devices"][block_device.name] = block_device

  return topology

if __name__ == "__main__":
  data = explore_sas_topology()
  pp = pprint.PrettyPrinter(width=120, compact=True)
  printable = {
    "enclosures": {k: v.__dict__ for k, v in data["enclosures"].items()},
    "block_devices": {k: v.__dict__ for k, v in data["block_devices"].items()}
  }
  pp.pprint(printable)
