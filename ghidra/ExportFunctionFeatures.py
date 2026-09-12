# Export non-byte structural features from an analyzed, lawfully dumped main.
# @category SSBU.Research
# @runtime PyGhidra
from __future__ import print_function
import json
import os
from collections import Counter
from ghidra.program.model.scalar import Scalar


def main():
    args = [str(arg) for arg in getScriptArgs()]
    if len(args) == 3:
        output, base_text, version = args
        base = toAddr(base_text)
    elif len(args) == 0:
        output = askFile("New features.jsonl (do not publish the full export)", "Save").getAbsolutePath()
        base = askAddress("Text base", "Exact start of main's executable .text block")
        version = askString("Version", "Version of the dumped game, e.g. 13.0.5")
    else:
        raise ValueError("Arguments: output.jsonl text_base game_version")
    if os.path.exists(output):
        raise ValueError("Output already exists; choose a new filename")
    if version not in ("13.0.4", "13.0.5"):
        raise ValueError("Expected a 13.0.4 reference or a 13.0.5 target")
    if str(currentProgram.getLanguage().getProcessor()) != "AARCH64" or currentProgram.getLanguage().isBigEndian():
        raise ValueError("Import and analyze as little-endian AARCH64 first")
    memory = currentProgram.getMemory()
    block = memory.getBlock(base)
    if block is None or not block.isExecute() or not block.isInitialized() or block.getStart() != base:
        raise ValueError("Text base must be the start of one initialized executable block")
    listing = currentProgram.getListing()
    count = 0
    with open(output, "w") as destination:
        destination.write(json.dumps({
            "type": "metadata", "schema": 1, "game_version": version,
            "text_base": str(base), "text_size": int(block.getSize()),
            "executable_sha256": currentProgram.getExecutableSHA256(),
            "language": str(currentProgram.getLanguageID()),
            "note": "Structural leads only; no bytes, ABI proof, or automatic hook approval."
        }) + "\n")
        functions = currentProgram.getFunctionManager().getFunctions(True)
        while functions.hasNext():
            monitor.checkCancelled()
            function = functions.next()
            entry = function.getEntryPoint()
            if not block.contains(entry) or function.isExternal():
                continue
            # Soft size lead is 560 bytes; retain a wide range and report the filter.
            size = int(function.getBody().getNumAddresses())
            if not 32 <= size <= 16384:
                continue
            mnemonics, constants, store_displacements, calls, data_refs = [], set(), set(), [], set()
            instructions = listing.getInstructions(function.getBody(), True)
            while instructions.hasNext():
                monitor.checkCancelled()
                instruction = instructions.next()
                mnemonic = str(instruction.getMnemonicString()).upper()
                mnemonics.append(mnemonic)
                for index in range(instruction.getNumOperands()):
                    for operand in instruction.getOpObjects(index):
                        if isinstance(operand, Scalar):
                            value = int(operand.getSignedValue())
                            if -65536 <= value <= 65535:
                                constants.add(value)
                                if mnemonic.startswith("ST") and index == instruction.getNumOperands() - 1:
                                    store_displacements.add(value)
                for ref in instruction.getReferencesFrom():
                    if ref.getReferenceType().isCall() and block.contains(ref.getToAddress()):
                        calls.append({"site": int(ref.getFromAddress().subtract(base)), "target": int(ref.getToAddress().subtract(base))})
                    elif ref.getReferenceType().isData():
                        data_refs.add(str(ref.getToAddress()))
            destination.write(json.dumps({
                "type": "function", "offset": int(entry.subtract(base)),
                "name": str(function.getName()), "size": size,
                "mnemonics": mnemonics, "histogram": dict(Counter(mnemonics)),
                "constants": sorted(constants), "store_displacements": sorted(store_displacements),
                "calls": calls, "data_references": sorted(data_refs),
                "blocks_note": "Store scalars include stack and unrelated bases; NOT proven buffer offsets."
            }) + "\n")
            count += 1
        destination.write(json.dumps({"type": "end", "function_count": count, "size_filter": [32, 16384]}) + "\n")
    println("Exported %d functions. Rank candidates, then independently inspect ABI and callers." % count)


main()
