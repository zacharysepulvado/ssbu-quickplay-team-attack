# Inspect ONE reviewed candidate and ONE direct BL caller. Never approves a hook.
# @category SSBU.Research
# @runtime PyGhidra
from __future__ import print_function
import json
import os


def bl_target(site, word):
    if word & 0xfc000000 != 0x94000000:
        return None
    immediate = word & 0x03ffffff
    if immediate & 0x02000000:
        immediate -= 0x04000000
    return site + immediate * 4


def main():
    args = [str(arg) for arg in getScriptArgs()]
    if len(args) == 5:
        output, base_text, entry_text, call_text, length_text = args
        base = toAddr(base_text)
        entry_offset, call_offset, length = int(entry_text, 0), int(call_text, 0), int(length_text, 0)
    elif len(args) == 0:
        output = askFile("New candidate.json", "Save").getAbsolutePath()
        base = askAddress("Text base", "Exact start of main's executable .text block")
        entry_offset = int(askString("Entry", "Candidate text-relative offset, e.g. 0x1234"), 0)
        call_offset = int(askString("Caller", "Direct BL instruction text-relative offset"), 0)
        length = askInt("Signature length", "16..64 bytes, multiple of 4")
    else:
        raise ValueError("Arguments: output.json text_base entry_offset call_offset signature_length")
    if os.path.exists(output):
        raise ValueError("Output exists; choose a new filename")
    if not 16 <= length <= 64 or length % 4 or entry_offset <= 0 or call_offset <= 0 or entry_offset % 4 or call_offset % 4:
        raise ValueError("Invalid offsets or signature length")
    if abs(entry_offset - call_offset) < length:
        raise ValueError("Entry and caller signatures overlap")
    if str(currentProgram.getLanguage().getProcessor()) != "AARCH64" or currentProgram.getLanguage().isBigEndian():
        raise ValueError("Expected little-endian AARCH64")
    memory = currentProgram.getMemory()
    block = memory.getBlock(base)
    if block is None or block.getStart() != base or not block.isExecute() or not block.isInitialized():
        raise ValueError("Text base is not the initialized executable block start")
    entry, call = base.add(entry_offset), base.add(call_offset)
    for address in (entry, call):
        if not block.contains(address) or not block.contains(address.add(length - 1)):
            raise ValueError("Signature lies outside this text block")
    manager = currentProgram.getFunctionManager()
    function = manager.getFunctionAt(entry)
    caller = manager.getFunctionContaining(call)
    if function is None or caller is None or caller == function:
        raise ValueError("Require a defined function entry and a separate caller")
    if not function.getBody().contains(entry.add(length - 1)) or not caller.getBody().contains(call.add(length - 1)):
        raise ValueError("Signature crosses a function boundary; shorten it or choose another caller")
    if bl_target(call_offset, int(memory.getInt(call)) & 0xffffffff) != entry_offset:
        raise ValueError("Caller does not begin with direct AArch64 BL to candidate")

    def signature(address):
        raw = getBytes(address, length)
        hits = []
        cursor = block.getStart()
        while cursor.compareTo(block.getEnd()) <= 0 and len(hits) < 2:
            monitor.checkCancelled()
            found = memory.findBytes(cursor, block.getEnd(), raw, None, True, monitor)
            if found is None:
                break
            if int(found.subtract(base)) % 4 == 0:
                hits.append(int(found.subtract(base)))
            cursor = found.add(1)
        if len(hits) != 1 or hits[0] != int(address.subtract(base)):
            raise ValueError("Signature is not unique; use more bytes or another callsite")
        return " ".join("%02X" % (int(byte) & 0xff) for byte in raw)

    result = {
        "schema": 1, "status": "UNVERIFIED_CANDIDATE", "game_version": "REVIEW_REQUIRED",
        "executable_sha256": currentProgram.getExecutableSHA256(),
        "text_base": str(base), "text_size": int(block.getSize()),
        "serializer_text_offset": entry_offset, "expected_prologue": signature(entry),
        "caller_text_offset": call_offset, "expected_callsite": signature(call),
        "direct_bl_verified": True, "signatures_unique_in_imported_block": True,
        "candidate_name": str(function.getName()), "inferred_prototype": str(function.getSignature()),
        "caller_name": str(caller.getName()), "reviewed_abi": "", "reviewed_buffer_len": 0,
        "evidence_reviewed": False, "capture_offsets": [],
        "required": ["Verify dump version", "Prove x0 output-pointer/void ABI in disassembly", "Prove initialized readable rule bytes", "Check consumer and globals", "Trace actual Quickplay path separately"]
    }
    with open(output, "w") as destination:
        json.dump(result, destination, indent=2, sort_keys=True)
    println("Saved an UNVERIFIED candidate. No config was enabled and no code was patched.")


main()
