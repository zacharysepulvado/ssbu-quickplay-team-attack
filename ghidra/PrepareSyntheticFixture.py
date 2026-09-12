# TEST ONLY. Run exclusively against make_synthetic_fixture.py output.
# @category SSBU.Research.Tests
# @runtime PyGhidra
from ghidra.program.model.address import AddressSet
from ghidra.program.model.symbol import SourceType

if currentProgram.getName() != "synthetic-aarch64.bin":
    raise ValueError("Refusing to modify any program except synthetic-aarch64.bin")
memory = currentProgram.getMemory()
blocks = list(memory.getBlocks())
if len(blocks) != 1 or blocks[0].getSize() != 4096:
    raise ValueError("Wrong synthetic fixture shape")
block = blocks[0]
# BinaryLoader's load address need not equal Program.getImageBase().
base = block.getStart()
# Additional identity checks before setting up this test-only analysis database.
if (int(memory.getInt(base.add(0x28))) & 0xffffffff) != 0xd2800f01 or (int(memory.getInt(base.add(0x88))) & 0xffffffff) != 0x97ffffe6:
    raise ValueError("Synthetic fixture markers missing")
block.setName(".text")
block.setExecute(True)
manager = currentProgram.getFunctionManager()
for offset, length, name in [(0x20, 36, "synthetic_serializer"), (0x80, 28, "synthetic_caller")]:
    entry = base.add(offset)
    disassemble(entry)
    if manager.getFunctionAt(entry) is None:
        manager.createFunction(name, entry, AddressSet(entry, entry.add(length - 1)), SourceType.USER_DEFINED)
println("Prepared original synthetic test functions; not Nintendo code.")
